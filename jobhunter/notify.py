"""Phone notifications via ntfy.sh (free, no account). Install the ntfy app,
subscribe to your topic name, and set NTFY_TOPIC to the same name.
Pick a long random topic name - anyone who knows it can read it."""
import logging

import requests

log = logging.getLogger("jobhunter")


def send(topic: str, title: str, message: str, url: str | None = None,
         priority: int = 3, tags: list[str] | None = None, server: str = "https://ntfy.sh"):
    if not topic:
        log.info("notify (no NTFY_TOPIC): %s - %s", title, message.splitlines()[0] if message else "")
        return False
    payload = {"topic": topic, "title": title, "message": message,
               "priority": priority, "tags": tags or []}
    if url:
        payload["click"] = url
        payload["actions"] = [{"action": "view", "label": "Open job", "url": url}]
    try:
        requests.post(server, json=payload, timeout=15).raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("ntfy failed: %s", e)
        return False


def job_alert(topic, job, urgent: bool):
    how = {"quick": "Quick apply on Reed", "short-form": "Short form on company site",
           "company-site": "Apply on company site"}.get(job.apply_type, "")
    age = job.age_hours()
    lines = [f"{job.company} · {job.location}",
             f"Salary: {job.salary_text()}" + (f" · {job.applicants} applicants" if job.applicants is not None else ""),
             (("Posted " + (f"{age:.0f}h ago" if age < 48 else f"{age / 24:.0f} days ago") + " · ")
              if age is not None else "") + how,
             "Why: " + "; ".join(job.reasons[:3])]
    return send(topic, f"{'🔥 ' if urgent else ''}{job.score}% {job.title}", "\n".join(lines),
                url=job.url, priority=5 if urgent else 4, tags=["briefcase"])


def digest(topic, jobs, dashboard_url: str | None = None):
    if not jobs:
        return False
    lines = [f"{j.score}% {j.title} – {j.company}" for j in jobs[:10]]
    more = f"\n+{len(jobs) - 10} more" if len(jobs) > 10 else ""
    return send(topic, f"{len(jobs)} more new matching jobs", "\n".join(lines) + more,
                url=dashboard_url, priority=2, tags=["clipboard"])
