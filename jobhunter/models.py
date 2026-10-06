from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Job:
    source: str               # reed / adzuna / greenhouse:monzo ...
    source_id: str
    title: str
    company: str
    location: str
    url: str
    posted_at: datetime | None = None
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    applicants: int | None = None
    apply_type: str = "unknown"   # quick / short-form / company-site / unknown
    # filled in later
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable id that also de-duplicates the same job seen on two sites."""
        norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
        return hashlib.sha1(f"{norm(self.title)}|{norm(self.company)}".encode()).hexdigest()[:12]

    def age_hours(self, now: datetime | None = None) -> float | None:
        if not self.posted_at:
            return None
        now = now or datetime.now(timezone.utc)
        return max(0.0, (now - self.posted_at).total_seconds() / 3600)

    def salary_text(self) -> str:
        if self.salary_min and self.salary_max and self.salary_max != self.salary_min:
            return f"£{self.salary_min:,.0f}–£{self.salary_max:,.0f}"
        if self.salary_min or self.salary_max:
            return f"£{(self.salary_min or self.salary_max):,.0f}"
        return "not listed"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        d["key"] = self.key
        d["salary_text"] = self.salary_text()
        return d
