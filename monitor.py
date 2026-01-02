import os
import re
import sys
import requests

VACANCY_THRESHOLD = int(os.getenv("VACANCY_THRESHOLD", "5"))

# You can later narrow this search (series/keyword/location). For now it checks recent postings.
SEARCH_URL = os.getenv("SEARCH_URL", "https://data.usajobs.gov/api/search?ResultsPerPage=50")

# This matches text like "49 vacancies"
VACANCY_RE = re.compile(r"(\d+)\s+vacancies?\b", re.IGNORECASE)

def must_env(name: str) -> str:
    v = os.getenv(name, "")
    v = v.strip()
    if not v:
        print(f"Missing required secret/environment variable: {name}")
        sys.exit(1)
    return v

def main():
    email = must_env("USAJOBS_EMAIL")
    key = must_env("USAJOBS_API_KEY")

    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": key,
        "Accept": "application/json",
    }

    r = requests.get(SEARCH_URL, headers=headers, timeout=30)
    if r.status_code != 200:
        print("USAJOBS API request failed.")
        print("Status:", r.status_code)
        print("Body (first 500 chars):", r.text[:500])
        sys.exit(1)

    items = r.json().get("SearchResult", {}).get("SearchResultItems", [])
    hits = []

    for item in items:
        d = item.get("MatchedObjectDescriptor", {}) or {}
        url = d.get("PositionURI")
        title = d.get("PositionTitle", "Unknown title")

        if not url:
            continue

        page = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
        m = VACANCY_RE.search(page)
        if not m:
            continue

        vacancies = int(m.group(1))
        if vacancies > VACANCY_THRESHOLD:
            hits.append(f"{vacancies} vacancies — {title}\n{url}")

    if hits:
        print("MATCHES FOUND (vacancies > threshold):\n")
        print("\n\n".join(hits))
        # Exit code 2 = intentional “alarm” so the workflow shows Red X
        sys.exit(2)

    print("No postings found over threshold.")
    sys.exit(0)

if __name__ == "__main__":
    main()
