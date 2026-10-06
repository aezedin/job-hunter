"""Application kit: a tailored cover-letter draft + checklist for one job.

It's a draft for YOU to read, edit and send - always check it before applying.
"""
from datetime import date

from .profile import skills_in

EVIDENCE = {
    "Troubleshooting": "troubleshooting and configuring systems in my own lab environments",
    "Customer service": "front-line support in my current role, resolving enquiries by phone and email",
    "Ticketing": "logging and following up issues through to resolution in my current role",
    "Incident response": "coordinating with teams and emergency services during live incidents at work",
    "GDPR": "handling sensitive personal data daily in line with GDPR",
    "Networking": "my Level 3 Diploma in Networking & Cybersecurity",
    "Wireshark": "analysing network traffic with Wireshark",
    "Nmap": "network discovery and scanning with Nmap",
    "Python": "writing Python scripts to automate tasks (Level 2 Digital Development, Distinction)",
    "Security+": "my CompTIA Security+ certification",
    "TryHackMe / HTB": "regular practice on TryHackMe and Hack The Box",
    "Vulnerability assessment": "vulnerability scanning exercises in my lab",
    "Documentation": "keeping clear, accurate records in a regulated housing setting",
    "Windows": "supporting Windows users and systems",
}


def cover_letter(job: dict, profile: dict) -> str:
    text = f"{job['title']} {job.get('description', '')}"
    wanted = skills_in(text)
    mine = set(profile.get("skills", [])) | {"Customer service", "Incident response", "GDPR", "Documentation"}
    matched = [s for s in wanted if s in mine and s in EVIDENCE][:4]
    if len(matched) < 3:
        matched += [s for s in ["Security+", "Customer service", "Troubleshooting", "Incident response"]
                    if s not in matched][: 3 - len(matched)]
    bullets = "\n".join(f"- {EVIDENCE[s][0].upper() + EVIDENCE[s][1:]}." for s in matched)
    gaps = [s for s in wanted if s not in mine]
    name = profile.get("name") or "Abdulhakim Ezedin"
    return f"""# {job['title']} – {job['company']}

**Link:** {job['url']}
**Salary:** {job.get('salary_text') or 'see advert'} · **Score:** {job.get('score')}% · **Apply type:** {job.get('apply_type')}

## Before you apply
- [ ] Read the full advert (the snippet the app sees may be cut short)
- [ ] Check the CV leads with the skills below
- [ ] Edit the letter so it sounds like you, then send
- [ ] Mark as applied: `python -m jobhunter status {job['key'][:6]} applied`
{('- [ ] They mention skills not on your CV: ' + ', '.join(gaps) + ' - add them only if you really have them') if gaps else ''}

## Cover letter draft

Dear Hiring Manager,

I'm applying for the {job['title']} role at {job['company']}. {profile.get('pitch', '')}

What I would bring to the role:

{bullets}

I'm studying for a BSc (Hons) in Cyber Security at the University of West London and want a role where I can apply that learning to real users and systems. My current job has taught me to stay calm under pressure, communicate clearly and follow procedures properly, which I know matter in {'a security team' if any(w in text.lower() for w in ['soc', 'security', 'cyber']) else 'a support team'}.

I would welcome the chance to discuss how I can help {job['company']}. Thank you for your time.

Kind regards,
{name}

_Draft generated {date.today():%d %b %Y}_
"""
