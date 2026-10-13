"""Employer career boards with public JSON feeds (Greenhouse, Lever, Ashby, Workday).

These are the companies' own job boards, so new roles appear here first.
"""
from datetime import datetime, timezone

import requests

from . import TIMEOUT, UA, get_json, log, parse_iso, strip_html
from ..models import Job


NAMES = {"mangroup": "Man Group", "wehrtyou": "Hudson River Trading", "jumptrading": "Jump Trading",
         "squarepointcapital": "Squarepoint Capital", "imc": "IMC Trading", "drweng": "DRW",
         "xtxmarketstechnologies": "XTX Markets", "recordedfuture": "Recorded Future", "huntress": "Huntress", "wizinc": "Wiz", "gocardless": "GoCardless", "truelayer": "TrueLayer",
         "mavensecuritiesholdingltd": "Maven Securities", "towerresearchcapital": "Tower Research Capital",
         "flowtraders": "Flow Traders", "marshallwace": "Marshall Wace", "gresearch": "G-Research",
         "qubeResearchTechnologies": "Qube Research & Technologies", "starlingbank": "Starling Bank",
         "checkoutcom": "Checkout.com", "thoughtmachine": "Thought Machine", "ocadotechnology": "Ocado Technology",
         "elevenlabs": "ElevenLabs", "search.jobs.barclays": "Barclays", "jobs.citi.com": "Citi",
         "careers.blackrock.com": "BlackRock", "jobs.natwestgroup.com": "NatWest Group",
         "careers.lloydsbankinggroup.com": "Lloyds Banking Group", "careers.astrazeneca.com": "AstraZeneca",
         "jobs.gsk.com": "GSK", "jobs.bt.com": "BT Group", "careers.mastercard.com": "Mastercard",
         "jobs.vodafone.com": "Vodafone", "careers.lseg.com": "LSEG", "careers.hsbc.com": "HSBC",
         "jobs.thalesgroup.com": "Thales", "careers.baesystems.com": "BAE Systems",
         "blackrock": "BlackRock", "bnymellon": "BNY", "citi": "Citi", "ms": "Morgan Stanley", "nomura": "Nomura",
         "mastercard": "Mastercard", "lseg": "LSEG", "spgi": "S&P Global", "crowdstrike": "CrowdStrike",
         "paloaltonetworks": "Palo Alto Networks", "mmc": "Marsh McLennan", "astrazeneca": "AstraZeneca",
         "gsk": "GSK", "schroders": "Schroders", "fil": "Fidelity International"}


def _name(slug):
    return NAMES.get(slug, slug.title())


def _is_london(loc: str) -> bool:
    loc = (loc or "").lower()
    return "london" in loc or loc.strip() in {"uk", "united kingdom", "remote (uk)", "uk remote"}


def greenhouse(slug: str) -> list[Job]:
    # Companies on Greenhouse's EU servers (job-boards.eu.greenhouse.io) use a separate API host
    try:
        data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    except Exception:  # noqa: BLE001
        data = get_json(f"https://boards-api.eu.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        if not _is_london(loc):
            continue
        out.append(Job(
            source=f"greenhouse:{slug}", source_id=str(j["id"]), title=j.get("title", ""),
            company=_name(slug), location=loc,
            url=j.get("absolute_url", ""),
            posted_at=parse_iso(j.get("first_published") or j.get("updated_at")),
            description=strip_html(j.get("content", "")), apply_type="short-form",
        ))
    return out


def lever(slug: str) -> list[Job]:
    data = get_json(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    out = []
    for j in data:
        cats = j.get("categories") or {}
        loc = cats.get("location", "") or ", ".join(cats.get("allLocations") or [])
        if not _is_london(loc):
            continue
        ts = j.get("createdAt")
        out.append(Job(
            source=f"lever:{slug}", source_id=j["id"], title=j.get("text", ""),
            company=_name(slug), location=loc, url=j.get("hostedUrl", ""),
            posted_at=datetime.fromtimestamp(ts / 1000, timezone.utc) if ts else None,
            description=j.get("descriptionPlain", "") or strip_html(j.get("description", "")),
            apply_type="short-form",
        ))
    return out


def ashby(slug: str) -> list[Job]:
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    out = []
    for j in data.get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        loc = next((l for l in locs if _is_london(l)), None)
        if not loc:
            continue
        out.append(Job(
            source=f"ashby:{slug}", source_id=j["id"], title=j.get("title", ""),
            company=_name(slug), location=loc, url=j.get("jobUrl", ""),
            posted_at=parse_iso(j.get("publishedAt")),
            description=j.get("descriptionPlain", ""), apply_type="short-form",
        ))
    return out


# Workday is what most banks, insurers and big firms use. Each board is written as
# "host/tenant/site", copied from the careers web address, e.g.
#   https://blackrock.wd1.myworkdayjobs.com/en-US/BlackRock_Professional
#   -> "blackrock.wd1.myworkdayjobs.com/blackrock/BlackRock_Professional"
WORKDAY_TERMS = ["intern", "spring", "insight", "summer", "first year"]
WORKDAY_MAX_DETAILS = 25  # adverts opened per board per run (keeps runs quick and polite)


def workday(entry: str) -> list[Job]:
    host, tenant, site = entry.strip("/").split("/")
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    seen = {}
    for term in WORKDAY_TERMS:
        r = requests.post(f"{base}/jobs", json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term},
                          headers={**UA, "Accept": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        for p in r.json().get("jobPostings", []):
            path = p.get("externalPath")
            loc = p.get("locationsText", "")
            # "3 Locations" can't be judged from the list - open the advert to check
            if path and (_is_london(loc) or "location" in loc.lower()):
                seen.setdefault(path, p)
    company = NAMES.get(tenant, tenant.replace("_", " ").title())
    out = []
    for path, p in list(seen.items())[:WORKDAY_MAX_DETAILS]:
        try:
            info = get_json(base + path, headers={"Accept": "application/json"}).get("jobPostingInfo", {})
        except Exception as e:  # noqa: BLE001
            log.warning("workday %s advert failed: %s", tenant, e)
            continue
        locs = [info.get("location", "")] + list(info.get("additionalLocations") or [])
        loc = next((l for l in locs if _is_london(l)), None)
        if not loc:
            continue
        out.append(Job(
            source=f"workday:{tenant}", source_id=str(info.get("jobReqId") or path), title=info.get("title") or p.get("title", ""),
            company=company, location=loc,
            url=info.get("externalUrl") or f"https://{host}/en-US/{site}{path}",
            posted_at=parse_iso(info.get("startDate")),
            description=strip_html(info.get("jobDescription", "")), apply_type="company-site",
        ))
    return out


# Radancy ("TalentBrew") careers sites, used by Barclays, Citi, BlackRock and many big
# employers. Their adverts look like  https://<site>/job/london/<title>/<id>/<id>
# and the site has a JSON search endpoint behind its search box.
RADANCY_TERMS = ["intern", "spring", "insight", "first year"]


def _ld_json_posting(html: str) -> dict:
    import json as _json
    import re as _re
    for m in _re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, _re.S | _re.I):
        try:
            d = _json.loads(m.group(1).strip())
        except ValueError:
            continue
        for item in (d if isinstance(d, list) else [d]):
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def radancy(site: str) -> list[Job]:
    import re as _re
    found = {}
    for term in RADANCY_TERMS:
        r = requests.get(f"https://{site}/search-jobs/results", headers={**UA, "Accept": "application/json",
                         "X-Requested-With": "XMLHttpRequest"}, timeout=TIMEOUT, params={
            "ActiveFacetID": 0, "CurrentPage": 1, "RecordsPerPage": 50, "Keywords": term,
            "SearchResultsModuleName": "Search Results", "SortCriteria": 0, "SortDirection": 0, "SearchType": 5})
        r.raise_for_status()
        html = r.json().get("results", "")
        for m in _re.finditer(r'<a[^>]+href="(/(?:[a-z]{2}(?:-[a-z]{2})?/)?job/([^/"]+)/[^"]+/\d+/(\d+))"[^>]*>(.*?)</a>', html, _re.S | _re.I):
            path, city, jid, inner = m.groups()
            if "london" in city.lower():
                found.setdefault(jid, (path, strip_html(inner)))
    company = NAMES.get(site, site.split(".")[-2].title() if site.count(".") >= 2 else site)
    out = []
    for jid, (path, title) in list(found.items())[:WORKDAY_MAX_DETAILS]:
        url, desc, posted = f"https://{site}{path}", "", None
        try:
            page = requests.get(url, headers=UA, timeout=TIMEOUT)
            page.raise_for_status()
            ld = _ld_json_posting(page.text)
            desc = strip_html(ld.get("description", "")) or strip_html(page.text)[:6000]
            posted = parse_iso(ld.get("datePosted"))
            title = title or ld.get("title", "")
        except Exception as e:  # noqa: BLE001
            log.warning("radancy %s advert failed: %s", site, e)
        out.append(Job(source=f"radancy:{site}", source_id=jid, title=title, company=company,
                       location="London", url=url, posted_at=posted, description=desc,
                       apply_type="company-site"))
    return out


def amazon(_: str = "") -> list[Job]:
    """amazon.jobs has a public search feed (includes AWS)."""
    from datetime import datetime as _dt
    out, seen = [], set()
    for term in ("intern", "internship", "spring"):
        d = get_json("https://www.amazon.jobs/en/search.json", params={
            "base_query": term, "loc_query": "London, United Kingdom", "result_limit": 100})
        for j in d.get("jobs", []):
            if j.get("id_icims") in seen or "london" not in (j.get("location") or "").lower():
                continue
            seen.add(j.get("id_icims"))
            try:
                posted = _dt.strptime(j.get("posted_date", ""), "%B %d, %Y").replace(tzinfo=timezone.utc)
            except ValueError:
                posted = None
            out.append(Job(source="amazon", source_id=str(j.get("id_icims")), title=j.get("title", ""),
                           company="Amazon" + (" (AWS)" if "aws" in (j.get("business_category") or "").lower() else ""),
                           location=j.get("location", ""), url="https://www.amazon.jobs" + j.get("job_path", ""),
                           posted_at=posted, apply_type="company-site",
                           description=strip_html(" ".join(j.get(k) or "" for k in (
                               "description", "basic_qualifications", "preferred_qualifications")))))
    return out


BOARD_COUNTS: dict[str, int | str] = {}  # per board: London jobs found, or "failed" (saved in docs/last_run.json)


def fetch(cfg: dict) -> list[Job]:
    jobs = []
    for kind, fn in (("greenhouse", greenhouse), ("lever", lever), ("ashby", ashby), ("workday", workday),
                     ("radancy", radancy), ("amazon", amazon)):
        for slug in cfg.get(kind, []):
            try:
                got = fn(slug)
                BOARD_COUNTS[f"{kind}:{slug}"] = len(got)
                jobs += got
            except Exception as e:  # noqa: BLE001
                BOARD_COUNTS[f"{kind}:{slug}"] = "failed"
                log.warning("%s:%s failed: %s", kind, slug, e)
    log.info("company boards: %d London jobs", len(jobs))
    return jobs
