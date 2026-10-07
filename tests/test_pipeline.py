"""Offline tests: fake API responses, run the whole pipeline. `python -m pytest`"""
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jobhunter.sources as src
from jobhunter import matcher, notify
from jobhunter.models import Job
from jobhunter.profile import years_required
from jobhunter.sources import adzuna, companies, reed

NOW = datetime.now(timezone.utc)
CFG = tomllib.loads((Path(__file__).parent.parent / "config.toml").read_text())
PROFILE = {"skills": ["Security+", "Troubleshooting", "Windows", "Networking", "Wireshark", "Nmap", "Python"]}


def J(**kw):
    base = dict(source="t", source_id="1", title="Cyber Security Summer Internship 2027", company="Acme Bank",
                location="London", url="https://x", posted_at=NOW - timedelta(days=3),
                description="10-week summer internship in our security operations team, June to August 2027. "
                            "Open to penultimate year students graduating in 2028. Paid.")
    base.update(kw)
    return Job(**base)


def test_good_internship_passes():
    assert matcher.reject_reason(J(), CFG, NOW) is None


def test_rejections():
    r = lambda **kw: matcher.reject_reason(J(**kw), CFG, NOW)
    assert r(title="1st Line IT Support Technician") == "not an internship"
    assert r(title="Marketing Summer Internship") == "wrong level or field"
    assert r(title="Summer Internship", description="Join our marketing events team.") == "not IT or cyber"
    assert r(contract_type="permanent") == "permanent role"
    assert r(company="Newto Training") == "training-course advert"
    assert r(description="Security internship. Proven experience with Splunk.").startswith("advert says")
    assert r(description="Security internship. CCNA certification is essential.") == "requires CCNA"
    assert r(description="Cyber internship for students graduating in 2027.").startswith("for students graduating")
    assert r(description="Cyber summer internship for students graduating in 2029.") is None
    assert r(description="Cyber internship, 12 month placement in industry.").startswith("advert says")
    # you have a licence and a car, so this must NOT be rejected
    assert r(description="Security summer internship. Full UK driving licence required.") is None


def test_years_regex():
    assert years_required("minimum 2 years experience") == 2
    assert years_required("no experience needed") is None


def test_scoring_prefers_cyber_and_fresh():
    a = matcher.score(J(posted_at=NOW - timedelta(hours=3), applicants=5), PROFILE, NOW)
    b = matcher.score(J(title="Technology Summer Internship", posted_at=NOW - timedelta(days=20)), PROFILE, NOW)
    assert a.score > b.score


def test_dedupe_same_job_two_sites():
    kept, _ = matcher.run([J(source="reed"), J(source="adzuna", company="Acme Bank plc")], CFG, PROFILE, NOW)
    assert len(kept) == 1


def test_sources_parse(monkeypatch):
    fake = {
        "reed": {"results": [{"jobId": 1, "jobTitle": "IT Intern", "employerName": "Foo",
                              "locationName": "London", "date": NOW.strftime("%d/%m/%Y"),
                              "jobDescription": "x", "applications": 7, "jobUrl": "https://reed/1"}]},
        "detail": {"jobDescription": "<p>Full advert text</p>", "contractType": "Temporary"},
        "adzuna": {"results": [{"id": "9", "title": "<strong>Security</strong> Intern", "company": {"display_name": "Bar"},
                                "location": {"display_name": "London"}, "redirect_url": "https://adz/9",
                                "created": NOW.isoformat(), "description": "d", "contract_type": "contract"}]},
        "greenhouse": {"jobs": [
            {"id": 5, "title": "Security Intern", "location": {"name": "London"}, "absolute_url": "https://gh/5",
             "first_published": NOW.isoformat(), "content": "&lt;p&gt;hi&lt;/p&gt;"},
            {"id": 6, "title": "Security Intern", "location": {"name": "New York"}, "absolute_url": "https://gh/6"}]},
    }

    def get_json(url, **kw):
        if "reed" in url:
            return fake["detail"] if "/jobs/" in url else fake["reed"]
        return fake["adzuna"] if "adzuna" in url else fake["greenhouse"]

    for m in (src, reed, adzuna, companies):
        monkeypatch.setattr(m, "get_json", get_json, raising=False)
    r = reed.fetch("k", ["it"], "London", 10)[0]
    assert r.applicants == 7 and r.apply_type == "quick"
    reed.enrich("k", [r])
    assert r.description == "Full advert text" and r.contract_type == "temporary"
    a = adzuna.fetch("i", "k", ["sec"], "London", 10, 72)[0]
    assert a.title == "Security Intern" and a.contract_type == "contract"
    g = companies.fetch({"greenhouse": ["foo"]})
    assert len(g) == 1 and g[0].description == "hi"


def test_notify_without_topic_is_safe():
    assert notify.job_alert("", J(score=80, reasons=["x"]), urgent=True) is False
