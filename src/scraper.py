"""
Gambian news scraper.

Politely walks four Gambian publications (The Point, Foroyaa, Gainako,
Standard) and harvests articles into a single CSV. Designed to fail
gracefully on individual page errors and respect server load via random
delays.

Usage:
    from src.scraper import scrape_all
    df = scrape_all(max_articles_per_source=2000)
"""

from __future__ import annotations

import logging
import random
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
        return bool(self.headline and self.text and self.url)


# ── Polite HTTP ──────────────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def _polite_get(url: str) -> requests.Response | None:
    """GET with timeout, random delay, and graceful failure."""
    try:
        time.sleep(random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS))
        r = _session.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            log.warning("non-200 from %s: %s", url, r.status_code)
            return None
        return r
    except Exception as e:  # noqa: BLE001
        log.warning("request failed for %s: %s", url, e)
        return None


# ── Per-source extractors ─────────────────────────────────────────────
#
# Each scraper yields Article objects. The HTML structures of these
# four sites change occasionally, so the selectors here are pragmatic,
# best-effort and fall back to <p> tags if a specific class isn't found.

def scrape_thepoint(max_articles: int = 2000) -> Iterator[Article]:
    """The Point Newspaper, https://thepoint.gm"""
    base = "https://thepoint.gm"
    seen: set[str] = set()
    for page in range(1, 200):
        list_url = f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        links = {urlparse.urljoin(base, a["href"]) for a in soup.select("h2 a, h3 a, .entry-title a") if a.get("href")}
        if not links:
            break
        new = links - seen
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_article(link, source="The Point")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


def scrape_foroyaa(max_articles: int = 2000) -> Iterator[Article]:
    """Foroyaa, https://foroyaa.net"""
    base = "https://foroyaa.net"
    seen: set[str] = set()
    for page in range(1, 200):
        list_url = f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        links = {urlparse.urljoin(base, a["href"]) for a in soup.select(".entry-title a, h2 a, h3 a") if a.get("href")}
        if not links:
            break
        new = links - seen
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_article(link, source="Foroyaa")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


def scrape_gainako(max_articles: int = 2000) -> Iterator[Article]:
    """Gainako, https://gainako.com"""
    base = "https://gainako.com"
    seen: set[str] = set()
    for page in range(1, 200):
        list_url = f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        links = {urlparse.urljoin(base, a["href"]) for a in soup.select(".entry-title a, h2 a") if a.get("href")}
        if not links:
            break
        new = links - seen
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_article(link, source="Gainako")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


def scrape_standard(max_articles: int = 2000) -> Iterator[Article]:
    """Standard Newspaper, https://standard.gm"""
    base = "https://standard.gm"
    seen: set[str] = set()
    for page in range(1, 200):
        list_url = f"{base}/page/{page}/"
        r = _polite_get(list_url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        links = {urlparse.urljoin(base, a["href"]) for a in soup.select("h2 a, h3 a, .post-title a, .entry-title a") if a.get("href")}
        if not links:
            break
        new = links - seen
        if not new:
            break
        for link in new:
            seen.add(link)
            art = _extract_article(link, source="Standard")
            if art and art.is_valid():
                yield art
            if len(seen) >= max_articles:
                return


# ── Generic article extractor ─────────────────────────────────────────


def _extract_article(url: str, source: str) -> Article | None:
    r = _polite_get(url)
    if r is None:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    # Headline: try a few common selectors
    h1 = soup.select_one("h1.entry-title, h1.post-title, h1") or soup.find("h1")
    headline = h1.get_text(strip=True) if h1 else ""

    # Date: <time> tag, otherwise meta tag
    date = None
    t = soup.find("time")
    if t and t.get("datetime"):
        date = t["datetime"][:10]
    if not date:
        m = soup.find("meta", attrs={"property": "article:published_time"})
        if m and m.get("content"):
            date = m["content"][:10]

    # Body: prefer .entry-content or .post-content, fall back to all <p>
    body_el = soup.select_one(".entry-content, .post-content, article")
    if body_el:
        paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    else:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paragraphs if p)

    # Category: meta tag
    category = None
    m = soup.find("meta", attrs={"property": "article:section"})
    if m and m.get("content"):
        category = m["content"]

    return Article(date=date, source=source, headline=headline, text=text, url=url, category=category)


# ── Aggregator ────────────────────────────────────────────────────────

SCRAPERS = {
    "The Point": scrape_thepoint,
    "Foroyaa": scrape_foroyaa,
    "Gainako": scrape_gainako,
    "Standard": scrape_standard,
}


def scrape_all(max_articles_per_source: int = 2000, sources: Iterable[str] | None = None) -> pd.DataFrame:
    """Run every scraper and return a single concatenated DataFrame."""
    sources = sources or SCRAPERS.keys()
    rows: list[dict] = []
    for name in sources:
        log.info("starting %s", name)
        try:
            for art in SCRAPERS[name](max_articles=max_articles_per_source):
                rows.append(art.__dict__)
                if len(rows) % 50 == 0:
                    log.info("collected %d articles total", len(rows))
        except Exception as e:  # noqa: BLE001
            log.exception("scraper %s crashed: %s", name, e)
    df = pd.DataFrame(rows)
    df.to_csv(RAW_CSV, index=False)
    log.info("saved %d rows to %s", len(df), RAW_CSV)
    return df


if __name__ == "__main__":
    scrape_all()
