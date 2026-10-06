"""Adzuna API (free key: developer.adzuna.com). Aggregates many UK job boards."""
from . import get_json, log, parse_iso, strip_html
from ..models import Job

API = "https://api.adzuna.com/v1/api/jobs/gb/search/1"


def fetch(app_id: str, app_key: str, terms: list[str], location: str,
          radius_miles: int, max_age_hours: int) -> list[Job]:
    if not (app_id and app_key):
        log.info("adzuna: no ADZUNA_APP_ID/ADZUNA_APP_KEY set, skipping")
        return []
    jobs = []
    for term in terms:
        try:
            data = get_json(API, params={
                "app_id": app_id, "app_key": app_key, "what": term,
                "where": location, "distance": int(radius_miles * 1.6),
                "max_days_old": max(1, max_age_hours // 24), "sort_by": "date",
                "results_per_page": 50, "content-type": "application/json",
            })
        except Exception as e:  # noqa: BLE001
            log.warning("adzuna %r failed: %s", term, e)
            continue
        for r in data.get("results", []):
            predicted = str(r.get("salary_is_predicted")) == "1"
            jobs.append(Job(
                source="adzuna", source_id=str(r.get("id")),
                title=strip_html(r.get("title", "")),
                company=(r.get("company") or {}).get("display_name", ""),
                location=(r.get("location") or {}).get("display_name", ""),
                url=r.get("redirect_url", ""),
                posted_at=parse_iso(r.get("created")),
                description=strip_html(r.get("description", "")),
                # Adzuna guesses salaries when none is advertised; ignore guesses
                salary_min=None if predicted else r.get("salary_min"),
                salary_max=None if predicted else r.get("salary_max"),
                apply_type="company-site",
                contract_type=r.get("contract_type") or "",
            ))
    log.info("adzuna: %d results", len(jobs))
    return jobs
