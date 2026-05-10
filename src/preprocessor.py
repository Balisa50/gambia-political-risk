"""
Text preprocessing pipeline.

Reads the raw scraped CSV, applies the cleaning rules described in the
project brief, and writes a clean dataset ready for feature engineering.

Pipeline:
    lowercase
    strip HTML, URLs, emails, special characters
    remove punctuation (keep apostrophes)
    tokenise
    drop English stopwords
    lemmatise (WordNet)
    drop tokens shorter than 2 chars
    drop empty rows
    de-duplicate by URL and headline similarity
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

import nltk
import pandas as pd
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

from .config import CLEAN_CSV, RAW_CSV

log = logging.getLogger(__name__)

# One-time NLTK assets. Idempotent; safe to call repeatedly.
for pkg in ("stopwords", "wordnet", "punkt", "punkt_tab", "omw-1.4"):
    try:
        nltk.data.find(pkg)
    except LookupError:
        try:
            nltk.download(pkg, quiet=True)
        except Exception:  # noqa: BLE001
            pass

_STOP = set(stopwords.words("english"))
_LEMMA = WordNetLemmatizer()

# Patterns
_HTML = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+|www\.\S+")
_EMAIL = re.compile(r"\S+@\S+")
_NON_TEXT = re.compile(r"[^a-z\s']")  # we lowercase first, so [a-z]
_MULTI_WS = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Apply the full cleaning pipeline to a single string."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = _HTML.sub(" ", text)
    text = _URL.sub(" ", text)
    text = _EMAIL.sub(" ", text)
    text = _NON_TEXT.sub(" ", text)
    text = _MULTI_WS.sub(" ", text).strip()
    return text


def tokenise(text: str) -> list[str]:
    tokens = word_tokenize(text)
    out = []
    for t in tokens:
        if len(t) < 2:
            continue
        if t in _STOP:
            continue
        out.append(_LEMMA.lemmatize(t))
    return out


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning to headline + text columns and return the trimmed df."""
    log.info("cleaning %d rows", len(df))
    df = df.copy()
    df["headline_clean"] = df["headline"].fillna("").map(clean_text)
    df["text_clean"] = df["text"].fillna("").map(clean_text)
    df["tokens"] = df["text_clean"].map(tokenise)
    df["tokens_str"] = df["tokens"].map(lambda xs: " ".join(xs))

    before = len(df)
    df = df[(df["headline_clean"].str.len() > 0) & (df["text_clean"].str.len() > 50)]
    log.info("dropped %d rows with empty headline or short text", before - len(df))

    # De-duplicate by URL first
    df = df.drop_duplicates(subset=["url"])
    # Then by headline (keep first)
    df = df.drop_duplicates(subset=["headline_clean"])
    log.info("after dedup: %d rows", len(df))

    # Parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    log.info("after date filter: %d rows; range %s to %s", len(df), df["date"].min(), df["date"].max())

    return df


def run() -> pd.DataFrame:
    df = pd.read_csv(RAW_CSV)
    cleaned = clean_dataframe(df)
    cleaned.to_csv(CLEAN_CSV, index=False)
    log.info("saved clean dataset to %s", CLEAN_CSV)
    return cleaned


if __name__ == "__main__":
    run()
