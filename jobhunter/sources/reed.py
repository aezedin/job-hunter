"""Reed.co.uk official Jobseeker API (free key: reed.co.uk/developers/jobseeker).

Reed is the only source here that reports how many people have applied,
which is how we skip the "100+ applicants" jobs.
"""
from datetime import datetime, timezone

from . import get_json, log
from ..models import Job

API = "https://www.reed.co.uk/api/1.0/search"


def _date(s):
    # Reed returns dd/mm/yyyy (no time) -> treat as midday UK that day
    try:
        return datetime.strptime(s, "%d/%m/%Y").replace(hour=12, tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch(api_key: str, terms: list[str], location: str, radius: int) -> list[Job]:
    if not api_key:
        log.info("reed: no REED_API_KEY set, skipping")
        return []
    jobs = []
    for term in terms:
        try:
            data = get_json(API, auth=(api_key, ""), params={
                "keywords": term, "locationName": location,
                "distanceFromLocation": radius, "resultsToTake": 100,
            })
        except Exception as e:  # noqa: BLE001
            log.warning("reed %r failed: %s", term, e)
            continue
        for r in data.get("results", []):
            ext = r.get("externalUrl")
            jobs.append(Job(
                source="reed", source_id=str(r.get("jobId")),
                title=r.get("jobTitle", ""), company=r.get("employerName", ""),
                location=r.get("locationName", ""),
                url=r.get("jobUrl") or f"https://www.reed.co.uk/jobs/{r.get('jobId')}",
                posted_at=_date(r.get("date")),
                description=r.get("jobDescription", ""),
                salary_min=r.get("minimumSalary"), salary_max=r.get("maximumSalary"),
                applicants=r.get("applications"),
                # No external URL = you apply on Reed with your Reed CV (quick apply)
                apply_type="company-site" if ext else "quick",
            ))
    log.info("reed: %d results", len(jobs))
    return jobs
