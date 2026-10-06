"""Job sources. Each returns a list[Job]; network errors are logged, not raised."""
import logging
import re
from datetime import datetime, timezone
from html import unescape

import requests

log = logging.getLogger("jobhunter")
UA = {"User-Agent": "job-hunter/1.0 (personal job search)"}
TIMEOUT = 20


def get_json(url, **kw):
    kw.setdefault("timeout", TIMEOUT)
    headers = {**UA, **kw.pop("headers", {})}
    r = requests.get(url, headers=headers, **kw)
    r.raise_for_status()
    return r.json()


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_iso(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
