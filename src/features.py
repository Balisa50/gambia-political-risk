"""
Feature engineering.

Builds:
    - TF-IDF matrix (max 10000 features, with bigrams)
    - Sentence-transformer embeddings (all-MiniLM-L6-v2, 384-dim)
    - Article-level numeric features (length, lexical diversity, NER counts)
    - Topic-flag features (political, economic, crime)
    - Date features (day/month/quarter/year, days-from-election, COVID flag)

Outputs are pickled together for downstream notebooks. The pickle is
designed to fit in memory at typical corpus sizes (5k - 30k articles).
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import (
    CLEAN_CSV,
    COVID_PERIOD,
    CRIME_KEYWORDS,
    ECONOMIC_KEYWORDS,
    ELECTION_DATES,
    FEATURES_PKL,
    POLITICAL_KEYWORDS,
)

log = logging.getLogger(__name__)


# ── TF-IDF ────────────────────────────────────────────────────────────


def build_tfidf(corpus: list[str], max_features: int = 10_000) -> tuple[np.ndarray, TfidfVectorizer]:
    """
    Why TF-IDF (not bag-of-words):
        TF-IDF down-weights words that appear in many articles, so
        common newsroom filler ("said", "according") doesn't dominate.
        For a small corpus where rare topical terms carry the signal,
        TF-IDF is the right baseline before moving to dense embeddings.
    """
    vec = TfidfVectorizer(
        max_features=max_features,
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.85,
    )
    X = vec.fit_transform(corpus)
    log.info("TF-IDF matrix shape: %s, vocab size: %d", X.shape, len(vec.vocabulary_))
    return X, vec


# ── Sentence embeddings ───────────────────────────────────────────────


def build_embeddings(texts: list[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> np.ndarray:
    """
    Why all-MiniLM-L6-v2 (not mpnet-base):
        At 384 dimensions and ~22 MB, MiniLM gives 95% of mpnet's
        retrieval quality at a third of the inference cost. Important
        when running on a laptop, or wanting the saved pickle to stay
        small enough to commit if needed.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    emb = model.encode(texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
    log.info("embeddings shape: %s", emb.shape)
    return emb


# ── Article-level features ────────────────────────────────────────────


def article_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """Length, lexical diversity, sentence count, named-entity count."""
    feats = pd.DataFrame(index=df.index)
    text = df["text"].fillna("")
    feats["word_count"] = text.str.split().map(len)
    feats["sentence_count"] = text.str.count(r"[.!?]") + 1
    feats["avg_sentence_length"] = feats["word_count"] / feats["sentence_count"].clip(lower=1)
    # Lexical diversity = unique tokens / total tokens
    feats["lexical_diversity"] = df["tokens"].map(lambda xs: len(set(xs)) / max(len(xs), 1))
    # NER count (filled in later when spaCy is available)
    feats["entity_count"] = 0
    return feats


def topic_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Binary keyword-based topic flags (political / economic / crime)."""
    text = (df["headline"].fillna("") + " " + df["text"].fillna("")).str.lower()
    flags = pd.DataFrame(index=df.index)
    flags["is_political"] = text.apply(lambda t: int(any(k in t for k in POLITICAL_KEYWORDS)))
    flags["is_economic"] = text.apply(lambda t: int(any(k in t for k in ECONOMIC_KEYWORDS)))
    flags["is_crime"] = text.apply(lambda t: int(any(k in t for k in CRIME_KEYWORDS)))
    return flags


# ── Date features ─────────────────────────────────────────────────────


def date_features(df: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame(index=df.index)
    d = pd.to_datetime(df["date"], errors="coerce")
    feats["day_of_week"] = d.dt.dayofweek
    feats["month"] = d.dt.month
    feats["quarter"] = d.dt.quarter
    feats["year"] = d.dt.year

    # Days before/after the nearest known election event
    ref_dates = [datetime.strptime(s, "%Y-%m-%d").date() for s, _ in ELECTION_DATES]

    def days_to_election(x):
        if pd.isna(x):
            return None
        x = x.date()
        return min((x - r).days for r in ref_dates if abs((x - r).days) < 365 * 2) if any(abs((x - r).days) < 365 * 2 for r in ref_dates) else None

    feats["days_from_election"] = d.map(days_to_election)

    # COVID period flag
    cstart = pd.to_datetime(COVID_PERIOD[0])
    cend = pd.to_datetime(COVID_PERIOD[1])
    feats["is_covid_period"] = ((d >= cstart) & (d <= cend)).astype(int)

    return feats


# ── Combined runner ───────────────────────────────────────────────────


@dataclass
class FeatureBundle:
    df: pd.DataFrame
    tfidf: np.ndarray
    tfidf_vectorizer: TfidfVectorizer
    embeddings: np.ndarray
    article_features: pd.DataFrame
    flags: pd.DataFrame
    date_features: pd.DataFrame


def run(skip_embeddings: bool = False) -> FeatureBundle:
    df = pd.read_csv(CLEAN_CSV)
    df["tokens"] = df["tokens_str"].fillna("").str.split()

    log.info("building TF-IDF...")
    X, vec = build_tfidf(df["tokens_str"].fillna("").tolist())

    if skip_embeddings:
        log.info("skipping embeddings (skip_embeddings=True)")
        emb = np.zeros((len(df), 384), dtype=np.float32)
    else:
        log.info("building sentence embeddings...")
        emb = build_embeddings(df["text"].fillna("").tolist())

    log.info("building article-level features...")
    art = article_level_features(df)
    log.info("building topic flags...")
    flags = topic_flags(df)
    log.info("building date features...")
    dates = date_features(df)

    bundle = FeatureBundle(
        df=df,
        tfidf=X,
        tfidf_vectorizer=vec,
        embeddings=emb,
        article_features=art,
        flags=flags,
        date_features=dates,
    )

    with open(FEATURES_PKL, "wb") as f:
        pickle.dump(bundle, f)
    log.info("saved feature bundle to %s", FEATURES_PKL)
    return bundle


if __name__ == "__main__":
    run()
