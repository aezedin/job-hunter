"""Offline tests: fake API responses, run the whole pipeline. `python -m pytest`"""
from datetime import datetime, timedelta, timezone

import jobhunter.sources as src
from jobhunter import matcher, notify
from jobhunter.models import Job
from jobhunter.profile import years_required
from jobhunter.sources import adzuna, companies, reed

NOW = datetime.now(timezone.utc)
CFG = {
    "search": {"max_age_hours": 72, "min_salary": 24000, "max_applicants": 60},
    "filters": {
        "title_must_include": ["it support", "service desk", "soc", "security analyst", "cyber", "intern", "1st line"],
        "title_exclude": ["senior", "lead", "manager"],
        "max_years_experience": 3,
    },
}
PROFILE = {"skills": ["Security+", "Troubleshooting", "Windows", "Networking", "Wireshark", "Nmap", "Python", "Ticketing"]}


def J(**kw):
    base = dict(source="t", source_id="1", title="IT Support Analyst", company="Acme", location="London",
                url="https://x", posted_at=NOW - timedelta(hours=3), description="Windows troubleshooting tickets")
    base.update(kw)
    return Job(**base)


def test_filters():
    run = lambda j: matcher.reject_reason(j, CFG, NOW)
    assert run(J()) is None
    assert run(J(title="Senior SOC Analyst")) == "too senior"
    assert run(J(title="Marketing Executive")) == "title not a target role"
    assert run(J(posted_at=NOW - timedelta(days=5))) == "too old"
    assert run(J(applicants=140)) == "140 applicants"
    assert run(J(salary_max=21000)) == "salary below floor"
    assert run(J(title="Cyber Security Intern", salary_max=18000)) is None  # interns exempt
    assert run(J(description="You will have 5+ years of IT support experience")) == "asks for 5+ years"


def test_years_regex():
    assert years_required("minimum 2 years experience") == 2
    assert years_required("3-5 years of relevant experience") == 3
    assert years_required("no experience needed") is None


def test_scoring_prefers_fresh_low_competition():
    a = matcher.score(J(applicants=4, description="Security+ Windows Wireshark ticket"), PROFILE, NOW)
    b = matcher.score(J(applicants=55, posted_at=NOW - timedelta(hours=60)), PROFILE, NOW)
    assert a.score > b.score
    assert any("applicants" in r for r in a.reasons)


def test_dedupe_same_job_two_sites():
    jobs = [J(source="reed"), J(source="adzuna", company="ACME ")]
    kept, _ = matcher.run(jobs, CFG, PROFILE, NOW)
    assert len(kept) == 1


def test_sources_parse(monkeypatch):
    fake = {
        "reed": {"results": [{"jobId": 1, "jobTitle": "1st Line Support", "employerName": "Foo",
                              "locationName": "London", "date": NOW.strftime("%d/%m/%Y"),
                              "jobDescription": "x", "minimumSalary": 26000, "maximumSalary": 28000,
                              "applications": 7, "jobUrl": "https://reed/1"}]},
        "adzuna": {"results": [{"id": "9", "title": "<strong>SOC</strong> Analyst", "company": {"display_name": "Bar"},
                                "location": {"display_name": "London"}, "redirect_url": "https://adz/9",
                                "created": NOW.isoformat(), "description": "d", "salary_min": 30000,
                                "salary_is_predicted": "1"}]},
        "greenhouse": {"jobs": [
            {"id": 5, "title": "Security Analyst", "location": {"name": "London"}, "absolute_url": "https://gh/5",
             "first_published": NOW.isoformat(), "content": "&lt;p&gt;hi&lt;/p&gt;"},
            {"id": 6, "title": "Security Analyst", "location": {"name": "New York"}, "absolute_url": "https://gh/6"}]},
    }

    def get_json(url, **kw):
        return fake["reed"] if "reed" in url else fake["adzuna"] if "adzuna" in url else fake["greenhouse"]

    for m in (src, reed, adzuna, companies):
        monkeypatch.setattr(m, "get_json", get_json, raising=False)
    r = reed.fetch("k", ["it"], "London", 10)[0]
    assert r.applicants == 7 and r.apply_type == "quick"
    a = adzuna.fetch("i", "k", ["soc"], "London", 10, 72)[0]
    assert a.title == "SOC Analyst" and a.salary_min is None  # predicted salary ignored
    g = companies.fetch({"greenhouse": ["foo"]})
    assert len(g) == 1 and g[0].description == "hi"


def test_notify_without_topic_is_safe():
    assert notify.job_alert("", J(score=80, reasons=["x"]), urgent=True) is False
