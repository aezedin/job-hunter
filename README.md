# Job Hunter

Finds **paid summer internships** in IT and cyber security in London that fit my CV and uni calendar, scores them, and sends a push notification to my phone, usually within about 2 hours of an advert going live.

Built because job-site alert emails arrive late, after 100+ people have already applied.

## What it does

| Step | How |
|---|---|
| Find jobs | Reed API, Adzuna API and Jooble API (both aggregate many UK boards), and employers' own career boards (Greenhouse, Lever, Ashby) |
| Filter | London only; title must be an internship/summer programme in IT or cyber; rejects permanent roles, year-long placements, unpaid roles, adverts asking for experience or certifications not on my CV, and internships for other graduation years. Reed adverts are checked in full, not just the preview |
| Score 0–100 | Target role, entry-level wording, overlap with CV skills, how fresh it is, how few applicants, how easy it is to apply |
| Notify | Push alert through [ntfy](https://ntfy.sh). Jobs scoring 70+ that are under 12h old get an urgent alert |
| Track | SQLite database plus a dashboard page on GitHub Pages: new, interested, applied, interview, offer |
| Help apply | `kit` writes a tailored cover-letter draft and checklist for a job |
| LinkedIn / Indeed | Pre-filtered search links (London, entry level, newest first, last hour/24h, Easy Apply). The app does not scrape LinkedIn or auto-apply, because LinkedIn's User Agreement bans bots and accounts get restricted for it |

## Setup (about 15 minutes)

1. **Free API keys**
   - Reed: https://www.reed.co.uk/developers/jobseeker
   - Adzuna: https://developer.adzuna.com/signup
2. **Phone alerts:** install the **ntfy** app (Android/iOS) and subscribe to a long, random topic name, e.g. `abdul-jobs-7Kq92xLm`. Anyone who knows the name can read it.
3. **GitHub:** create a new repo, upload these files, then go to *Settings → Secrets and variables → Actions* and add these secrets:
   `REED_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `NTFY_TOPIC`, and optionally `JOOBLE_API_KEY` (free from https://jooble.org/api/about)
4. **Dashboard:** go to *Settings → Pages → Deploy from branch → main / docs*. Add a repository *variable* `DASHBOARD_URL` with the Pages URL.
5. **Test it:** go to *Actions → Job hunt → Run workflow*. After that it runs every 2 hours from 07:00 to 23:00 UK time.

> Privacy: `.gitignore` keeps CV files (`*.docx`, `*.pdf`) and cover-letter drafts out of GitHub. Only `profile.toml` (name and skills list) is uploaded.

## Run it on your laptop

```bash
pip install -r requirements.txt
python -m jobhunter profile "Abdulhakim_Ezedin_IT_Support_CV.docx"   # refresh skills from CV
set REED_API_KEY=...   (Windows)   |   export REED_API_KEY=...   (Mac/Linux)
python -m jobhunter run
python -m jobhunter list
python -m jobhunter kit a53c16              # cover letter draft -> kits/
python -m jobhunter status a53c16 applied
python -m jobhunter links                   # fresh LinkedIn/Indeed searches
python -m pytest                            # tests
```

To change what it looks for (search terms, salary floor, applicant limit, companies), edit `config.toml`.

## Project layout

```
jobhunter/
  sources/   reed.py, adzuna.py, companies.py (Greenhouse/Lever/Ashby)
  matcher.py filtering + scoring
  profile.py CV -> skills profile
  store.py   SQLite tracker
  notify.py  ntfy push alerts
  kit.py     cover-letter drafts
  links.py   LinkedIn/Indeed fresh-search links
  dashboard.py static HTML dashboard
.github/workflows/hunt.yml   scheduled run every 2h
```
