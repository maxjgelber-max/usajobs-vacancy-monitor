import requests
import re
import os

VACANCY_THRESHOLD = 10

SEARCH_URL = "https://data.usajobs.gov/api/search?ResultsPerPage=50"

HEADERS = {
    "Host": "data.usajobs.gov",
    "User-Agent": os.environ["USAJOBS_EMAIL"].strip(),
    "Authorization-Key": os.environ["USAJOBS_API_KEY"].strip(),
}


VACANCY_RE = re.compile(r"(\d+)\s+vacancies?", re.IGNORECASE)

def main():
    r = requests.get(SEARCH_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()

    items = data["SearchResult"]["SearchResultItems"]

    alerts = []

    for item in items:
        d = item["MatchedObjectDescriptor"]
        url = d.get("PositionURI")

        if not url:
            continue

        page = requests.get(url, timeout=30).text
        match = VACANCY_RE.search(page)

        if not match:
            continue

        vacancies = int(match.group(1))

        if vacancies > VACANCY_THRESHOLD:
            alerts.append(
                f"{d['PositionTitle']} ({vacancies} vacancies)\n{url}\n"
            )

    if alerts:
        message = "\n".join(alerts)
        requests.post(
            "https://api.github.com/repos/{repo}/issues".format(
                repo=os.environ["GITHUB_REPO"]
            ),
            headers={
                "Authorization": f"token {os.environ['GITHUB_TOKEN']}"
            },
            json={
                "title": "USAJOBS vacancy alert",
                "body": message
            }
        )

if __name__ == "__main__":
    main()
