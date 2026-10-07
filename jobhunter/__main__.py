"""Job Hunter command line.

  python -m jobhunter profile path/to/CV.docx   build profile.toml from your CV
  python -m jobhunter run                       search, score, store, notify
  python -m jobhunter list [status]             show tracked jobs
  python -m jobhunter status <id> <status>      e.g. status 3fa9c1 applied
  python -m jobhunter kit <id>                  write a cover-letter draft
  python -m jobhunter links                     print fresh LinkedIn/Indeed links
"""
import argparse
import json
import logging
from datetime import datetime, timezone
import os
import sys
import tomllib
from pathlib import Path

from . import dashboard, kit, links, matcher, notify, profile
from .sources import adzuna, companies, jooble, reed
from .store import STATUSES, Store

ROOT = Path(os.environ.get("JOBHUNTER_HOME", Path(__file__).resolve().parent.parent))
log = logging.getLogger("jobhunter")


def load_cfg():
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    notify.RADAR_URL = cfg.get("notify", {}).get("radar_url", "")
    return cfg


def cmd_run(args):
    cfg, prof = load_cfg(), profile.load(ROOT / "profile.toml")
    s = cfg["search"]
    report = []  # one line per source, shown on the GitHub run page

    def source(name, needs_key, fn):
        if needs_key is False:
            report.append(f"| {name} | ⚠️ skipped: key missing (add it under Settings → Secrets) | 0 |")
            return []
        jobs = fn()
        report.append(f"| {name} | ✅ checked | {len(jobs)} |")
        return jobs

    reed_key = os.getenv("REED_API_KEY", "")
    az_id, az_key = os.getenv("ADZUNA_APP_ID", ""), os.getenv("ADZUNA_APP_KEY", "")
    found = []
    found += source("Reed", bool(reed_key), lambda: reed.fetch(
        reed_key, s["search_terms"], s["location"], s["radius_miles"]))
    found += source("Adzuna", bool(az_id and az_key), lambda: adzuna.fetch(
        az_id, az_key, s.get("adzuna_terms", s["search_terms"]), s["location"], s["radius_miles"], s["max_age_hours"]))
    jooble_key = os.getenv("JOOBLE_API_KEY", "")
    found += source("Jooble", bool(jooble_key), lambda: jooble.fetch(
        jooble_key, s.get("jooble_terms", s.get("adzuna_terms", s["search_terms"])), s["location"], s["radius_miles"]))
    found += source("Company career pages", None, lambda: companies.fetch(cfg.get("companies", {})))

    # Pass 1: cheap title checks, then fetch full Reed adverts for what's left
    candidates = [j for j in found if not matcher.title_reason(j, cfg)]
    if reed_key:
        reed.enrich(reed_key, [j for j in candidates if j.source == "reed"])
    kept, rejected = matcher.run(found, cfg, prof)
    store = Store(ROOT / "data" / "jobs.db")
    now = datetime.now(timezone.utc)
    hidden = store.recheck_new(lambda j: matcher.reject_reason(j, cfg, now))
    if hidden:
        print(f"Hid {hidden} saved job(s) that no longer match the filters")
    new = store.add_new(kept)
    skipped = ", ".join(f"{v} {k}" for k, v in sorted(rejected.items(), key=lambda x: -x[1])) or "none"
    print(f"Found {len(found)} · kept {len(kept)} · NEW {len(new)} · skipped: {skipped}")

    topic, n = os.getenv("NTFY_TOPIC", ""), cfg["notify"]
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        lines = ["## Job hunt report", "", "| Source | Status | Jobs found |", "|---|---|---|", *report,
                 "", f"**{len(found)}** found → **{len(kept)}** fit your filters → **{len(new)}** new",
                 "", f"Filtered out: {skipped}",
                 "", "Phone alerts: " + ("✅ on" if topic else "⚠️ off (add NTFY_TOPIC secret)"), ""]
        lines += [f"- {j.score}% [{j.title} – {j.company}]({j.url})" for j in new[:20]]
        with open(summary_file, "a") as fh:
            fh.write("\n".join(lines) + "\n")
    # Saved in the repo too, so problems can be diagnosed without the Actions log
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "last_run.json").write_text(json.dumps({
        "at": datetime.now(timezone.utc).isoformat(), "sources": report,
        "found": len(found), "kept": len(kept), "new": len(new), "filtered_out": rejected,
        "warnings": _warnings[-30:], "alerts_on": bool(topic),
        "sample_rejected_titles": sorted({j.title for j in found if j not in kept})[:40],
    }, indent=1))

    alerts = [j for j in new if j.score >= n["min_score_to_alert"]]
    for j in alerts[:8]:  # individual alerts for the best; the rest go in a digest
        age = j.age_hours()
        notify.job_alert(topic, j, urgent=j.score >= n["urgent_score"] and (age is None or age < 12))
    notify.digest(topic, alerts[8:], os.getenv("DASHBOARD_URL"))
    store.mark_notified([j.key for j in alerts])

    for j in new:
        print(f"  {j.score:>3}% {j.key[:6]} {j.title} – {j.company} [{j.salary_text()}] {j.url}")
    dashboard.build(store.all(), s["search_terms"], ROOT / "docs")


def cmd_summary(args):
    """Send one alert per internship you haven't dealt with yet (status 'new' or
    'interested'), best first - a clean list for your phone."""
    from .models import Job
    from .sources import parse_iso
    load_cfg()  # sets the Job Radar button link
    topic = os.getenv("NTFY_TOPIC", "")
    rows = [r for r in Store(ROOT / "data" / "jobs.db").all() if r["status"] in ("new", "interested")]
    rows.sort(key=lambda r: r.get("score", 0))  # lowest first, so the best ends up on top
    notify.send(topic, f"✅ Updated list: {len(rows)} summer internships that fit you",
                "Older alerts from the first test runs can be cleared. Only these match your rules "
                "(paid summer internship, London, IT/cyber, nothing you lack).",
                url=os.getenv("DASHBOARD_URL"), priority=3, tags=["white_check_mark"])
    fields = Job.__dataclass_fields__
    for r in rows:
        kw = {k: v for k, v in r.items() if k in fields}
        kw["posted_at"] = parse_iso(r.get("posted_at"))
        notify.job_alert(topic, Job(**kw), urgent=False)
    print(f"Sent summary of {len(rows)} jobs")


def cmd_list(args):
    for r in Store(ROOT / "data" / "jobs.db").all(args.status):
        print(f"{r['score']:>3}% {r['key'][:6]} [{r['status']:<10}] {r['title']} – {r['company']}  {r['url']}")


def cmd_status(args):
    n = Store(ROOT / "data" / "jobs.db").set_status(args.id, args.status, args.notes)
    print(f"Updated {n} job(s)" if n else "No job with that id")


def cmd_kit(args):
    store, prof = Store(ROOT / "data" / "jobs.db"), profile.load(ROOT / "profile.toml")
    job = store.get(args.id)
    if not job:
        sys.exit("No job with that id")
    out = ROOT / "kits" / f"{job['key'][:6]}-{job['company'][:20].replace(' ', '_')}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(kit.cover_letter(job, prof))
    store.set_status(job["key"], "interested")
    print(f"Wrote {out}")


def cmd_links(args):
    for l in links.all_links(load_cfg()["search"]["search_terms"]):
        print(f"\n{l['term']}\n  LinkedIn last hour: {l['linkedin_1h']}\n  LinkedIn Easy Apply: {l['linkedin_easy']}\n  Indeed 24h: {l['indeed_24h']}")


def cmd_profile(args):
    p = profile.build_profile(Path(args.cv), ROOT / "profile.toml")
    print(f"Saved profile.toml for {p['name']}: {', '.join(p['skills'])}")


_warnings: list[str] = []


class _Keep(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.WARNING:
            import re  # never save API keys: drop query strings from URLs
            _warnings.append(re.sub(r"\?\S*", "?…", record.getMessage())[:300])


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger().addHandler(_Keep())
    ap = argparse.ArgumentParser(prog="jobhunter")
    sub = ap.add_subparsers(required=True)
    sub.add_parser("run").set_defaults(fn=cmd_run)
    p = sub.add_parser("list"); p.add_argument("status", nargs="?", choices=STATUSES); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("status"); p.add_argument("id"); p.add_argument("status", choices=STATUSES)
    p.add_argument("--notes"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("kit"); p.add_argument("id"); p.set_defaults(fn=cmd_kit)
    sub.add_parser("links").set_defaults(fn=cmd_links)
    sub.add_parser("summary").set_defaults(fn=cmd_summary)
    p = sub.add_parser("profile"); p.add_argument("cv"); p.set_defaults(fn=cmd_profile)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
