"""Filter out jobs that don't fit, then score the rest 0-100 against your CV."""
from datetime import datetime, timezone

from .models import Job
from .profile import skills_in, years_required

CORE_TITLES = ["it support", "service desk", "helpdesk", "help desk", "1st line", "first line",
               "desktop support", "soc", "security analyst", "cyber security analyst",
               "security operations", "penetration", "pen test"]
ENTRY_WORDS = ["graduate", "junior", "entry", "intern", "apprentice", "trainee", "placement",
               "1st line", "first line", "no experience"]
EXEMPT_FROM_SALARY = ["intern", "apprentice", "placement", "graduate scheme"]


def reject_reason(job: Job, cfg: dict, now: datetime) -> str | None:
    s, f = cfg["search"], cfg["filters"]
    title = job.title.lower()
    if not any(w in title for w in f["title_must_include"]):
        return "title not a target role"
    if any(w in title for w in f["title_exclude"]):
        return "too senior"
    age = job.age_hours(now)
    if age is not None and age > s["max_age_hours"]:
        return "too old"
    if job.applicants is not None and job.applicants > s["max_applicants"]:
        return f"{job.applicants} applicants"
    top = job.salary_max or job.salary_min
    # Reed sometimes reports hourly/daily rates; only compare annual-looking figures
    if top and top > 1000 and top < s["min_salary"] and not any(w in title for w in EXEMPT_FROM_SALARY):
        return "salary below floor"
    yrs = years_required(job.description)
    if yrs is not None and yrs >= f["max_years_experience"]:
        return f"asks for {yrs}+ years"
    return None


def score(job: Job, profile: dict, now: datetime) -> Job:
    title, text = job.title.lower(), f"{job.title} {job.description}".lower()
    pts, why = 0, []

    if any(w in title for w in CORE_TITLES):
        pts += 35; why.append("core target role")
    else:
        pts += 20
    if any(w in text for w in ENTRY_WORDS):
        pts += 10; why.append("entry-level")

    mine = set(profile.get("skills", []))
    wanted = set(skills_in(text))
    overlap = sorted(mine & wanted)
    if overlap:
        pts += min(25, 5 * len(overlap)); why.append("skills: " + ", ".join(overlap[:5]))
    if "security+" in text or "security plus" in text:
        pts += 5; why.append("mentions Security+")

    age = job.age_hours(now)
    if age is not None:
        if age < 6: pts += 15; why.append("posted <6h ago")
        elif age < 24: pts += 10; why.append("posted today")
        elif age < 48: pts += 5

    if job.applicants is not None:
        if job.applicants < 10: pts += 10; why.append(f"only {job.applicants} applicants")
        elif job.applicants < 25: pts += 6; why.append(f"{job.applicants} applicants")
        elif job.applicants < 50: pts += 2

    if job.apply_type in ("quick", "short-form"):
        pts += 5

    job.score, job.reasons = min(100, pts), why
    return job


def run(jobs: list[Job], cfg: dict, profile: dict, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    kept, rejected, seen = [], {}, set()
    for j in jobs:
        if j.key in seen:
            continue
        seen.add(j.key)
        why = reject_reason(j, cfg, now)
        if why:
            rejected[why] = rejected.get(why, 0) + 1
            continue
        kept.append(score(j, profile, now))
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept, rejected
