"""Filter out jobs that don't fit, then score the rest 0-100 against your CV.

Filtering happens in two passes:
  1. title_reason()  - cheap checks on title/company (before fetching anything)
  2. reject_reason() - everything, run on the FULL advert text where available
"""
import re
from datetime import datetime, timezone

from .models import Job
from .profile import skills_in, years_required

CORE_TITLES = ["cyber", "security", "soc", "it support", "service desk", "infrastructure",
               "network", "technology", "it intern"]
REQUIRED_WORDS = ["required", "essential", "must", "mandatory", "you will need", "you'll need"]


def has(text: str, terms) -> bool:
    """Whole-word-ish match: 'soc' matches 'SOC Analyst' but not 'Associate'."""
    text = (text or "").lower()
    for t in terms:
        t = t.strip().lower()
        right = r"(?![a-z])" if len(t) <= 4 else ""
        if re.search(r"(?<![a-z])" + re.escape(t) + right, text):
            return True
    return False


def _sentences(text: str):
    return re.split(r"(?<=[.!?•\n])\s+", (text or "").lower())


def title_reason(job: Job, cfg: dict) -> str | None:
    f = cfg["filters"]
    title = job.title.lower()
    if not has(title, f["title_must_include"]):
        return "not an internship"
    if has(title, f["title_exclude"]):
        return "wrong level or field"
    if any(w in (job.company or "").lower() for w in f.get("company_exclude", [])):
        return "training-course advert"
    return None


def reject_reason(job: Job, cfg: dict, now: datetime) -> str | None:
    s, f = cfg["search"], cfg["filters"]
    why = title_reason(job, cfg)
    if why:
        return why
    text = f"{job.title} {job.description}".lower()

    if not has(text, f.get("field_must_include", [])):
        return "not IT or cyber"
    if (job.contract_type or "").lower() in f.get("reject_contract_types", []):
        return "permanent role"
    age = job.age_hours(now)
    if age is not None and age > s["max_age_hours"]:
        return "too old"
    if job.applicants is not None and job.applicants > s["max_applicants"]:
        return "too many applicants"
    for p in f.get("reject_phrases", []):
        if p in text:
            return f"advert says '{p}'"
    for sent in _sentences(text):
        if any(w in sent for w in REQUIRED_WORDS):
            for cert in f.get("certs_not_held", []):
                if has(sent, [cert]):
                    return f"requires {cert.upper()}"
    yrs = years_required(job.description)
    if yrs is not None and yrs >= f.get("max_years_experience", 1):
        return "asks for experience"
    grad = f.get("graduation_year")
    if grad:
        for sent in _sentences(text):
            if "graduat" in sent:
                years = {int(y) for y in re.findall(r"\b(20[2-3]\d)\b", sent)}
                if years and grad not in years and not (min(years) < grad < max(years)):
                    return f"for students graduating {', '.join(map(str, sorted(years)))}"
    if any(w in (job.company or "").lower() for w in f.get("company_exclude", [])):
        return "training-course advert"
    return None


def score(job: Job, profile: dict, now: datetime) -> Job:
    title, text = job.title.lower(), f"{job.title} {job.description}".lower()
    pts, why = 0, []

    if has(title, ["cyber", "security", "soc"]):
        pts += 40; why.append("cyber security internship")
    elif has(title, CORE_TITLES):
        pts += 30; why.append("IT/tech internship")
    else:
        pts += 20; why.append("internship")
    if "summer" in text or re.search(r"\b(june|july|august)\b", text):
        pts += 10; why.append("summer dates")
    if any(w in text for w in ["penultimate", "first year", "1st year", "any year", "all years"]):
        pts += 10; why.append("open to your year")

    mine = set(profile.get("skills", []))
    overlap = sorted(mine & set(skills_in(text)))
    if overlap:
        pts += min(20, 5 * len(overlap)); why.append("skills: " + ", ".join(overlap[:4]))
    if "security+" in text or "security plus" in text:
        pts += 5; why.append("mentions Security+")

    age = job.age_hours(now)
    if age is not None:
        if age < 24: pts += 10; why.append("posted today")
        elif age < 72: pts += 5; why.append("posted this week")
    if job.applicants is not None and job.applicants < 25:
        pts += 5; why.append(f"only {job.applicants} applicants")
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
            bucket = why if not why.startswith(("advert says", "requires", "for students")) else why.split(" '")[0].split(" 20")[0]
            rejected[bucket] = rejected.get(bucket, 0) + 1
            continue
        kept.append(score(j, profile, now))
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept, rejected
