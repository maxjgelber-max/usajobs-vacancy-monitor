import json
import os
import sys
from pathlib import Path

import requests

VACANCY_THRESHOLD = int(os.getenv("VACANCY_THRESHOLD", "10"))
DATE_POSTED_DAYS = int(os.getenv("DATE_POSTED_DAYS", "1"))  # scan "everything" newly posted
RESULTS_PER_PAGE = int(os.getenv("RESULTS_PER_PAGE", "500"))  # max supported by API docs
MAX_PAGES = int(os.getenv("MAX_PAGES", "50"))  # safety cap so a run doesn't go wild

SEEN_FILE = Path("seen.json")

def must_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        print(f"Missing required secret/environment variable: {name}")
        sys.exit(1)
    return v

def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen_ids", []))
    except Exception:
        return set()

def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(
        json.dumps({"seen_ids": sorted(seen)}, indent=2),
        encoding="utf-8"
    )

def api_get_page(headers: dict, page: int) -> dict:
    url = (
        "https://data.usajobs.gov/api/search"
        f"?DatePosted={DATE_POSTED_DAYS}"
        f"&ResultsPerPage={RESULTS_PER_PAGE}"
        f"&Page={page}"
    )
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        print("USAJOBS API request failed.")
        print("Status:", r.status_code)
        print("Body (first 500 chars):", r.text[:500])
        sys.exit(1)
    return r.json()

def main():
    email = must_env("USAJOBS_EMAIL")
    key = must_env("USAJOBS_API_KEY")

    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": key,
        "Accept": "application/json",
    }

    seen = load_seen()
    new_hits = []
    total_scanned = 0

    # Page through results posted in the last N days
    for page in range(1, MAX_PAGES + 1):
        data = api_get_page(headers, page)
        items = data.get("SearchResult", {}).get("SearchResultItems", [])
        if not items:
            break

        for item in items:
            total_scanned += 1
            job_id = str(item.get("MatchedObjectId", "")).strip()
            d = item.get("MatchedObjectDescriptor", {}) or {}

            vacancies = d.get("NumberOfVacancies")
            if vacancies is None:
                continue

            try:
                vacancies = int(vacancies)
            except Exception:
                continue

            if vacancies < VACANCY_THRESHOLD:
                continue

            # Dedupe alerts
            if job_id and job_id in seen:
                continue

            title = d.get("PositionTitle", "Unknown title")
            agency = d.get("OrganizationName", "Unknown agency")
            close = d.get("ApplicationCloseDate", "Unknown close date")
            url = d.get("PositionURI", "")

            new_hits.append(
                f"{vacancies} vacancies — {title} ({agency})\nCloses: {close}\n{url}"
            )
            if job_id:
                seen.add(job_id)

    save_seen(seen)

    print(f"Scanned {total_scanned} postings from last {DATE_POSTED_DAYS} day(s).")
    if new_hits:
        print("\nMATCHES FOUND (new, not previously alerted):\n")
        print("\n\n".join(new_hits))
        # Exit 2 to “alarm” the workflow and trigger notification
        sys.exit(2)

    print(f"No NEW postings found with vacancies >= {VACANCY_THRESHOLD}.")
    sys.exit(0)

if __name__ == "__main__":
    main()
