"""Jooble API (free key: request one at https://jooble.org/api/about).
Jooble collects jobs from many UK sites, including some that have no API."""
import hashlib

import requests

from . import UA, TIMEOUT, log, parse_iso, strip_html
from ..models import Job

API = "https://jooble.org/api/{key}"


def fetch(api_key: str, terms: list[str], location: str, radius_miles: int) -> list[Job]:
    if not api_key:
        log.info("jooble: no JOOBLE_API_KEY set, skipping")
        return []
    jobs = []
    for term in terms:
        try:
            r = requests.post(API.format(key=api_key), headers=UA, timeout=TIMEOUT, json={
                "keywords": term, "location": location,
                "radius": str(int(radius_miles * 1.6)), "page": "1", "ResultOnPage": "50",
            })
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            log.warning("jooble %r failed: %s", term, str(e).split("?")[0].replace(api_key, "…"))
            continue
        for j in data.get("jobs", []):
            link = j.get("link", "")
            jobs.append(Job(
                source="jooble",
                source_id=str(j.get("id") or hashlib.sha1(link.encode()).hexdigest()[:12]),
                title=strip_html(j.get("title", "")), company=j.get("company", "") or "",
                location=j.get("location", "") or "", url=link,
                posted_at=parse_iso(j.get("updated")),
                description=strip_html(j.get("snippet", "")),
                apply_type="company-site",
                contract_type=(j.get("type") or "").lower(),
            ))
    log.info("jooble: %d results", len(jobs))
    return jobs
