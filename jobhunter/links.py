"""Pre-filtered search links for sites that don't allow automated access.

LinkedIn's User Agreement bans bots and scraping, and accounts get restricted
for it, so the app never touches LinkedIn. Instead these links open LinkedIn
(and Indeed) already filtered to London, entry level, newest first, posted
in the last few hours - the same "be early" advantage, one tap away.
"""
from urllib.parse import urlencode

def linkedin(term: str, hours: int = 24, easy_apply_only: bool = False) -> str:
    q = {"keywords": term, "location": "London, England, United Kingdom",
         "f_TPR": f"r{hours * 3600}",  # posted within N seconds
         "f_E": "1,2",                  # internship, entry level
         "sortBy": "DD"}                # newest first
    if easy_apply_only:
        q["f_AL"] = "true"
    return "https://www.linkedin.com/jobs/search/?" + urlencode(q)


def indeed(term: str, days: int = 1) -> str:
    return "https://uk.indeed.com/jobs?" + urlencode({"q": term, "l": "London", "fromage": days, "sort": "date"})


def all_links(terms: list[str]) -> list[dict]:
    return [{"term": t,
             "linkedin_1h": linkedin(t, 1),
             "linkedin_24h": linkedin(t, 24),
             "linkedin_easy": linkedin(t, 24, easy_apply_only=True),
             "indeed_24h": indeed(t)} for t in terms]
