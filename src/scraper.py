"""
Gambian news scraper.

Politely walks Gambian publications and harvests articles into a single
CSV. Designed to fail gracefully on individual page errors and respect
server load via random delays.

Site-specific selectors and URL patterns because each publication uses
different markup. Gainako is currently excluded due to a broken SSL
certificate on their server (cert is valid for a different hostname);
will be re-enabled when their hosting is fixed.

Usage:
    from src.scraper import scrape_all
    df = scrape_all(max_articles_per_source=250)
"""

from __future__ import annotations

import logging
import random
import re
import time
import urllib.parse as urlparse
from dataclasses import dataclass
from typing import Iterable, Iterator

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .config import (
    DELAY_MAX_SECONDS,
    DELAY_MIN_SECONDS,
    RAW_CSV,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass
class Article:
    date: str | None
    source: str
    headline: str
    text: str
    url: str
    category: str | None = None

    def is_valid(self) -> bool:
        return bool(self.headline and self.text and self.url and len(self.text) > 200)


# ── Polite HTTP ──────────────────────────────────────────────────────


_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def _polite_get(url: str, verify: bool = True) -> requests.Response | None:
    """GET with timeout, random delay, and graceful failure."""
    try:
        time.sleep(random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS))
        r = _session.get(url, timeout=REQUEST_TIMEOUT, verify=verify)
        if r.status_code != 200:
            log.warning("non-200 from %s: %s", url, r.status_code)
            return None
        # Force UTF-8 because requests' apparent_encoding heuristic
        # mis-detects Gambian sites as ASCII and corrupts curly quotes
        r.encoding = "utf-8"
        return r
    except Exception as e:  # noqa: BLE001
        log.warning("request failed for %s: %s", url, e)
        return None


# ── The Point Newspaper, custom CMS ──────────────────────────────────


_THEPOINT_PATH = re.compile(r"^/africa/gambia/(headline-news|national|sports|opinion|business|editorial|world|cartoon)/[a-z0-9-]+", re.I)


def scrape_thepoint(max_articles: int = 250) -> Iterator[Article]:
    base = "https://thepoint.gm"
    seen: set[str] = set()
    # Walk index pages by date
    for page in range(1, 30):
        list_url = base if page == 1 else f"{base}/page/{page}"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        # Collect all anchors that look like article paths
        candidates = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                if _THEPOINT_PATH.match(href):
                    candidates.append(urlparse.urljoin(base, href))
            elif "/africa/gambia/" in href and _THEPOINT_PATH.search(href):
                candidates.append(href)
        new = [c for c in dict.fromkeys(candidates) if c not in seen]
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_thepoint(link)
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


def _extract_thepoint(url: str) -> Article | None:
    from datetime import date as _date

    r = _polite_get(url)
    if r is None:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    h1 = soup.find("h1")
    headline = h1.get_text(strip=True) if h1 else ""

    date = None
    m = soup.find("meta", attrs={"property": "article:published_time"})
    if m and m.get("content"):
        date = m["content"][:10]
    if not date:
        t = soup.find("time")
        if t and t.get("datetime"):
            date = t["datetime"][:10]
    # The Point doesn't always expose published date via meta. We're
    # scraping from the front-page index, so the article is recent. Use
    # today's scrape date as a fallback rather than dropping the row.
    if not date:
        date = _date.today().isoformat()

    # Body: collect <p> from the main article container
    body_el = soup.find("article") or soup.find("div", class_=re.compile(r"article|content|entry|post-body", re.I))
    if body_el:
        paras = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    else:
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paras if p and len(p) > 30)

    # Category from URL
    cat = None
    parts = urlparse.urlparse(url).path.split("/")
    for p in parts:
        if p in {"headline-news", "national", "sports", "opinion", "business", "editorial", "world", "cartoon"}:
            cat = p.replace("-", " ").title()
            break

    return Article(date=date, source="The Point", headline=headline, text=text, url=url, category=cat)


# ── Foroyaa, WordPress ───────────────────────────────────────────────


def scrape_foroyaa(max_articles: int = 250) -> Iterator[Article]:
    base = "https://foroyaa.net"
    seen: set[str] = set()
    for page in range(1, 50):
        list_url = base if page == 1 else f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        anchors = soup.select("h3.entry-title a, h2.entry-title a, h2 a")
        links = [urlparse.urljoin(base, a["href"]) for a in anchors if a.get("href") and "/category/" not in a["href"] and "/author/" not in a["href"]]
        new = [l for l in dict.fromkeys(links) if l not in seen]
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_wp(link, source="Foroyaa")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


# ── Standard Newspaper, WordPress ────────────────────────────────────


def scrape_standard(max_articles: int = 250) -> Iterator[Article]:
    base = "https://standard.gm"
    seen: set[str] = set()
    for page in range(1, 50):
        list_url = base if page == 1 else f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        anchors = soup.select("h3.entry-title a, h2.entry-title a, h2 a")
        links = [urlparse.urljoin(base, a["href"]) for a in anchors if a.get("href") and "/category/" not in a["href"] and "/author/" not in a["href"]]
        new = [l for l in dict.fromkeys(links) if l not in seen]
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_wp(link, source="Standard")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


# ── The Fatu Network, WordPress ──────────────────────────────────────


def scrape_fatu_network(max_articles: int = 250) -> Iterator[Article]:
    base = "https://fatunetwork.net"
    seen: set[str] = set()
    for page in range(1, 50):
        list_url = base if page == 1 else f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        anchors = soup.select("h3.entry-title a, h2.entry-title a, h2 a")
        links = [urlparse.urljoin(base, a["href"]) for a in anchors if a.get("href") and "/category/" not in a["href"] and "/author/" not in a["href"] and "/tag/" not in a["href"]]
        new = [l for l in dict.fromkeys(links) if l not in seen]
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_wp(link, source="Fatu Network")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


# ── Kerr Fatou Media, WordPress ──────────────────────────────────────


def scrape_kerr_fatou(max_articles: int = 250) -> Iterator[Article]:
    base = "https://kerrfatou.com"
    seen: set[str] = set()
    for page in range(1, 50):
        list_url = base if page == 1 else f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        anchors = soup.select("h3.entry-title a, h2.entry-title a, h2 a")
        links = [urlparse.urljoin(base, a["href"]) for a in anchors if a.get("href") and "/category/" not in a["href"] and "/author/" not in a["href"] and "/tag/" not in a["href"]]
        new = [l for l in dict.fromkeys(links) if l not in seen]
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_wp(link, source="Kerr Fatou")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


# ── Kaironews, WordPress ─────────────────────────────────────────────


def scrape_kaironews(max_articles: int = 250) -> Iterator[Article]:
    base = "https://kaironews.com"
    seen: set[str] = set()
    for page in range(1, 50):
        list_url = base if page == 1 else f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        anchors = soup.select("h3.entry-title a, h2.entry-title a, h2 a")
        links = [urlparse.urljoin(base, a["href"]) for a in anchors if a.get("href") and "/category/" not in a["href"] and "/author/" not in a["href"] and "/tag/" not in a["href"]]
        new = [l for l in dict.fromkeys(links) if l not in seen]
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_wp(link, source="Kaironews")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


# ── Generic WordPress extractor ──────────────────────────────────────


def _extract_wp(url: str, source: str) -> Article | None:
    r = _polite_get(url)
    if r is None:
        return None
    soup = BeautifulSoup(r.text, "lxml")

    h1 = soup.select_one("h1.entry-title, h1.post-title") or soup.find("h1")
    headline = h1.get_text(strip=True) if h1 else ""

    date = None
    m = soup.find("meta", attrs={"property": "article:published_time"})
    if m and m.get("content"):
        date = m["content"][:10]
    if not date:
        t = soup.find("time")
        if t and t.get("datetime"):
            date = t["datetime"][:10]

    body_el = soup.select_one(".entry-content, .post-content, article")
    if body_el:
        paras = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    else:
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paras if p and len(p) > 30)

    cat = None
    m = soup.find("meta", attrs={"property": "article:section"})
    if m and m.get("content"):
        cat = m["content"]

    return Article(date=date, source=source, headline=headline, text=text, url=url, category=cat)


# ── Aggregator ────────────────────────────────────────────────────────

SCRAPERS = {
    "The Point": scrape_thepoint,
    "Foroyaa": scrape_foroyaa,
    "Standard": scrape_standard,
    "Fatu Network": scrape_fatu_network,
    "Kerr Fatou": scrape_kerr_fatou,
    "Kaironews": scrape_kaironews,
}


def scrape_all(max_articles_per_source: int = 250, sources: Iterable[str] | None = None) -> pd.DataFrame:
    """Run every scraper and return a single concatenated DataFrame."""
    sources = sources or SCRAPERS.keys()
    rows: list[dict] = []
    for name in sources:
        log.info("starting %s", name)
        try:
            count_before = len(rows)
            for art in SCRAPERS[name](max_articles=max_articles_per_source):
                rows.append(art.__dict__)
                if (len(rows) - count_before) % 25 == 0:
                    log.info("[%s] %d articles", name, len(rows) - count_before)
            log.info("[%s] finished with %d articles", name, len(rows) - count_before)
        except Exception as e:  # noqa: BLE001
            log.exception("scraper %s crashed: %s", name, e)
    df = pd.DataFrame(rows)
    df.to_csv(RAW_CSV, index=False)
    log.info("saved %d rows to %s", len(df), RAW_CSV)
    return df


if __name__ == "__main__":
    scrape_all(max_articles_per_source=250)
