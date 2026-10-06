"""SQLite storage: remembers every job seen and where you are with it."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ["new", "interested", "applied", "interview", "offer", "rejected", "skipped"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  key TEXT PRIMARY KEY,
  first_seen TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  notified INTEGER NOT NULL DEFAULT 0,
  notes TEXT DEFAULT '',
  data TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add_new(self, jobs) -> list:
        """Insert jobs not seen before; return only the new ones."""
        new = []
        now = datetime.now(timezone.utc).isoformat()
        seen_urls = {json.loads(r[0]).get("url") for r in self.db.execute("SELECT data FROM jobs")}
        for j in jobs:
            if j.url in seen_urls:  # same advert saved before (maybe under an older id)
                continue
            cur = self.db.execute(
                "INSERT OR IGNORE INTO jobs(key, first_seen, data) VALUES (?,?,?)",
                (j.key, now, json.dumps(j.to_dict())))
            if cur.rowcount:
                new.append(j)
        self.db.commit()
        return new

    def mark_notified(self, keys):
        self.db.executemany("UPDATE jobs SET notified=1 WHERE key=?", [(k,) for k in keys])
        self.db.commit()

    def set_status(self, key_prefix: str, status: str, notes: str | None = None) -> int:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        q = "UPDATE jobs SET status=?" + (", notes=?" if notes is not None else "") + " WHERE key LIKE ?"
        args = [status] + ([notes] if notes is not None else []) + [key_prefix + "%"]
        n = self.db.execute(q, args).rowcount
        self.db.commit()
        return n

    def all(self, status: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM jobs", []
        if status:
            q, a = q + " WHERE status=?", [status]
        rows = []
        for r in self.db.execute(q + " ORDER BY first_seen DESC", a):
            d = json.loads(r["data"])
            d.update(status=r["status"], first_seen=r["first_seen"], notes=r["notes"])
            rows.append(d)
        return rows

    def get(self, key_prefix: str) -> dict | None:
        for d in self.all():
            if d["key"].startswith(key_prefix):
                return d
        return None

    def recheck_new(self, reject_fn) -> int:
        """Re-apply the current filters to jobs still marked 'new' and hide the
        ones that no longer fit (e.g. after config.toml changes)."""
        from .models import Job
        from .sources import parse_iso
        fields = Job.__dataclass_fields__
        hidden = 0
        for d in self.all("new"):
            kw = {k: v for k, v in d.items() if k in fields}
            kw["posted_at"] = parse_iso(d.get("posted_at"))
            if reject_fn(Job(**kw)):
                hidden += self.set_status(d["key"], "skipped", notes="auto-hidden: no longer matches filters")
        return hidden

