"""Builds docs/index.html (a static page, published free with GitHub Pages)
and docs/jobs.json (machine-readable feed)."""
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .links import all_links

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mute:#5d6470;--line:#e3e6ea;--acc:#0b6e4f;--hot:#c2410c}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--card:#1b1e23;--ink:#eceef1;--mute:#9aa1ad;--line:#2b2f36;--acc:#3ccf91;--hot:#fb923c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
main{max-width:980px;margin:auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--mute);margin-bottom:18px}.bar{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 14px}
.bar button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:20px;padding:5px 12px;cursor:pointer}
.bar button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.job{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:8px;display:grid;grid-template-columns:52px 1fr;gap:12px}
.sc{font-weight:700;font-size:18px;color:var(--acc);text-align:center}.sc.hot{color:var(--hot)}
.t a{color:var(--ink);font-weight:600;text-decoration:none}.t a:hover{text-decoration:underline}
.m{color:var(--mute);font-size:13px}.why{font-size:13px;margin-top:3px}
.pill{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:10px;padding:0 7px;margin-left:6px;color:var(--mute)}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:16px 0}
summary{cursor:pointer;font-weight:600}table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
td{padding:5px 4px;border-top:1px solid var(--line)}td a{color:var(--acc)}
"""


def build(rows: list[dict], terms: list[str], out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r.get("status") != "new", -r.get("score", 0)))
    (out_dir / "jobs.json").write_text(json.dumps(
        {"updated": datetime.now(timezone.utc).isoformat(), "jobs": rows}, indent=1, default=str))

    cards = []
    for r in rows:
        hot = r.get("score", 0) >= 70
        sal = r.get("salary_text") or "salary not listed"
        apps = f" · {r['applicants']} applicants" if r.get("applicants") is not None else ""
        posted = (r.get("posted_at") or "")[:16].replace("T", " ")
        cards.append(f"""<div class="job" data-status="{escape(r.get('status','new'))}">
<div class="sc{' hot' if hot else ''}">{r.get('score',0)}</div>
<div><div class="t"><a href="{escape(r['url'])}" target="_blank" rel="noopener">{escape(r['title'])}</a>
<span class="pill">{escape(r.get('status','new'))}</span><span class="pill">{escape(r.get('apply_type',''))}</span></div>
<div class="m">{escape(r['company'])} · {escape(r['location'])} · {escape(sal)}{apps} · posted {escape(posted)} · id {r['key'][:6]}</div>
<div class="why">{escape('; '.join(r.get('reasons', [])))}</div></div></div>""")

    link_rows = "".join(
        f"<tr><td>{escape(l['term'])}</td><td><a href='{escape(l['linkedin_1h'])}' target=_blank>LinkedIn 1h</a></td>"
        f"<td><a href='{escape(l['linkedin_24h'])}' target=_blank>LinkedIn 24h</a></td>"
        f"<td><a href='{escape(l['linkedin_easy'])}' target=_blank>Easy Apply</a></td>"
        f"<td><a href='{escape(l['indeed_24h'])}' target=_blank>Indeed 24h</a></td></tr>"
        for l in all_links(terms))

    now = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Job Hunter</title><style>{CSS}</style></head>
<body><main><h1>Job Hunter</h1><div class="sub">{len(rows)} jobs tracked · updated {now}</div>
<div class="bar" id="bar"></div><div id="list">{''.join(cards) or '<p>No jobs yet.</p>'}</div>
<details><summary>Fresh LinkedIn &amp; Indeed searches</summary>
<table>{link_rows}</table></details></main>
<script>
const S=["all","new","interested","applied","interview","offer","rejected","skipped"],bar=document.getElementById("bar");
S.forEach(s=>{{const b=document.createElement("button");b.textContent=s;b.onclick=()=>{{
[...bar.children].forEach(x=>x.classList.toggle("on",x===b));
document.querySelectorAll(".job").forEach(j=>j.style.display=(s==="all"||j.dataset.status===s)?"":"none")}};bar.append(b)}});
bar.children[1].click();
</script></body></html>"""
    (out_dir / "index.html").write_text(html)
