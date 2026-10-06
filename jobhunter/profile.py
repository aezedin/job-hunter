"""Your CV -> a small skills profile used for matching.

The CV itself (with your phone/email) stays on your computer and is never
committed. Only profile.toml (name, target roles, skills) is used in the cloud.
"""
import re
import tomllib
from pathlib import Path

# Skills the matcher knows about. Synonyms map to one canonical name.
SKILL_VOCAB = {
    "Security+": ["security+", "comptia security", "sec+"],
    "Troubleshooting": ["troubleshoot"],
    "Windows": ["windows", "windows 10", "windows 11"],
    "Active Directory": ["active directory", "entra", "azure ad"],
    "Office 365": ["office 365", "microsoft 365", "o365", "m365"],
    "Networking": ["networking", "tcp/ip", "dns", "dhcp", "lan", "network"],
    "Wireshark": ["wireshark"],
    "Nmap": ["nmap"],
    "Python": ["python"],
    "Linux": ["linux", "bash"],
    "Ticketing": ["ticket", "servicenow", "jira", "zendesk", "freshservice", "itsm"],
    "ITIL": ["itil"],
    "Customer service": ["customer service", "customer-facing", "end user", "end-user"],
    "Incident response": ["incident response", "incident handling", "incident management"],
    "Documentation": ["documentation", "knowledge base"],
    "GDPR": ["gdpr", "data protection"],
    "Vulnerability assessment": ["vulnerabilit"],
    "SIEM": ["siem", "splunk", "sentinel", "qradar", "elastic"],
    "Burp Suite": ["burp"],
    "Metasploit": ["metasploit"],
    "TryHackMe / HTB": ["tryhackme", "hack the box", "hackthebox"],
    "Risk": ["risk"],
    "Hardware": ["hardware", "laptop", "printer", "peripheral"],
    "Cloud / AWS": ["aws", "azure", "cloud"],
}


def skills_in(text: str) -> list[str]:
    t = (text or "").lower()
    return [name for name, pats in SKILL_VOCAB.items() if any(p in t for p in pats)]


def read_docx(path: Path) -> str:
    import docx  # python-docx
    d = docx.Document(str(path))
    return "\n".join(p.text for p in d.paragraphs)


def build_profile(cv_path: Path, out: Path, name: str | None = None) -> dict:
    text = read_docx(cv_path) if cv_path.suffix == ".docx" else cv_path.read_text()
    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    name = name or first_line.title()
    skills = skills_in(text)
    body = (
        f'name = "{name}"\n'
        f"skills = {skills!r}\n".replace("'", '"')
        + '# One-line pitch used at the top of cover letters\n'
        + 'pitch = "I am a CompTIA Security+ certified Cyber Security student (University of West London) with front-line support experience and hands-on lab work in Nmap, Wireshark and Python."\n'
    )
    out.write_text(body)
    return {"name": name, "skills": skills}


def load(path: Path) -> dict:
    if not path.exists():
        return {"name": "", "skills": [], "pitch": ""}
    return tomllib.loads(path.read_text())


def years_required(text: str) -> int | None:
    """Largest 'N+ years' experience requirement found in a description."""
    hits = re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs)['’]?\s*(?:of\s+)?(?:\w+\s+){0,3}experience",
                      (text or "").lower())
    return max(map(int, hits)) if hits else None
