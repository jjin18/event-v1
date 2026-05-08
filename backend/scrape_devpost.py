"""Scrape projects from a Devpost hackathon page."""
import re
import time
from typing import Generator

import requests
from bs4 import BeautifulSoup


def _get(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; HackathonJudge/1.0)"}
    r = requests.get(url, headers=headers, timeout=15, **kwargs)
    r.raise_for_status()
    return r


def scrape_gallery_page(base_url: str, page: int) -> list[dict]:
    url = f"{base_url.rstrip('/')}/project-gallery?page={page}"
    r = _get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    projects = []
    for item in soup.select("li.software-item, div.gallery-item"):
        title_el = item.select_one("h5.software-entry-name a, h5 a, .entry-name a")
        title = title_el.get_text(strip=True) if title_el else "Unknown"
        link = title_el["href"] if title_el and title_el.get("href") else ""
        if link and not link.startswith("http"):
            link = "https://devpost.com" + link

        team_el = item.select_one(".software-entry-info span, .members")
        team = team_el.get_text(strip=True) if team_el else ""
        team = re.sub(r"\s+", " ", team).strip()

        desc_el = item.select_one(".software-entry-description, .tagline")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        track_el = item.select_one(".software-award-badge, .award-label")
        track = track_el.get_text(strip=True) if track_el else ""

        projects.append(
            {
                "title": title,
                "team_name": team,
                "description": desc[:400],
                "devpost_url": link,
                "track": track,
                "table_number": "",
            }
        )
    return projects


def _total_pages(base_url: str) -> int:
    url = f"{base_url.rstrip('/')}/project-gallery"
    r = _get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    last = soup.select("ul.pagination li:last-child a")
    if last:
        try:
            return int(last[0].get_text(strip=True))
        except ValueError:
            pass
    return 1


def scrape_all(base_url: str) -> Generator[dict, None, None]:
    """Yield status dicts and finally project dicts."""
    try:
        total = _total_pages(base_url)
    except Exception as e:
        yield {"error": str(e)}
        return

    all_projects = []
    for page in range(1, total + 1):
        yield {"status": f"Fetching page {page} of {total}..."}
        try:
            projects = scrape_gallery_page(base_url, page)
            all_projects.extend(projects)
            time.sleep(0.5)
        except Exception as e:
            yield {"status": f"Page {page} error: {e}"}

    yield {"status": "done", "projects": all_projects}


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else ""
    if not url:
        print("Usage: python scrape_devpost.py <devpost_hackathon_url>")
        sys.exit(1)
    for item in scrape_all(url):
        print(item)
