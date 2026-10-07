"""Employer career boards with public JSON feeds (Greenhouse, Lever, Ashby).

These are the companies' own job boards, so new roles appear here first.
"""
from datetime import datetime, timezone

from . import get_json, log, parse_iso, strip_html
from ..models import Job


NAMES = {"mangroup": "Man Group", "wehrtyou": "Hudson River Trading", "jumptrading": "Jump Trading",
         "squarepointcapital": "Squarepoint Capital", "imc": "IMC Trading", "drweng": "DRW",
         "xtxmarketstechnologies": "XTX Markets", "recordedfuture": "Recorded Future", "huntress": "Huntress", "wizinc": "Wiz", "gocardless": "GoCardless", "truelayer": "TrueLayer"}


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


def fetch(cfg: dict) -> list[Job]:
    jobs = []
    for kind, fn in (("greenhouse", greenhouse), ("lever", lever), ("ashby", ashby)):
        for slug in cfg.get(kind, []):
            try:
                jobs += fn(slug)
            except Exception as e:  # noqa: BLE001
                log.warning("%s:%s failed: %s", kind, slug, e)
    log.info("company boards: %d London jobs", len(jobs))
    return jobs
