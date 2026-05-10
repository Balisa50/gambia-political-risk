"""
Political Risk Index (PRI) construction.

Aggregates sentiment + topic signals at a weekly cadence and combines
them into a single 0-100 score where higher means a more stable,
positive news environment.

Weights (justified in README):
    mean sentiment             40%
    1 - negative_proportion    30%
    1 - political_prevalence   20%   (more political coverage = more stress)
    1 - crime_prevalence       10%   (more crime coverage = more stress)
"""

from __future__ import annotations

import logging
import pickle

import numpy as np
import pandas as pd

from .config import (
    ELECTION_DATES,
    FEATURES_PKL,
    PRI_CSV,
    SENTIMENT_CSV,
    TOPICS_CSV,
)
from .features import FeatureBundle  # noqa: F401  needed for pickle.load

log = logging.getLogger(__name__)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    sent = pd.read_csv(SENTIMENT_CSV, parse_dates=["date"])
    topics = pd.read_csv(TOPICS_CSV, parse_dates=["date"])
    df = sent.merge(topics, on=["url", "date"], how="inner")
    return df, df


def weekly_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per ISO week."""
    df = df.copy()
    df["week"] = df["date"].dt.to_period("W").apply(lambda r: r.start_time)

    # If distilBERT label exists use it; else fall back to VADER label
    if "label_db" in df.columns:
        df["sent_label"] = df["label_db"].str.lower()
        df["sent_score"] = df["score_db"]
    else:
        df["sent_label"] = df["vader_text_label"]
        df["sent_score"] = df["vader_text_compound"]

    # Load flags (political/crime/economic)
    with open(FEATURES_PKL, "rb") as f:
        bundle = pickle.load(f)
    flags = bundle.flags.copy()
    flags["url"] = bundle.df["url"]
    df = df.merge(flags, on="url", how="left")

    grouped = df.groupby("week").agg(
        n=("url", "count"),
        mean_sent=("sent_score", "mean"),
        neg_share=("sent_label", lambda s: (s == "negative").mean()),
        political_share=("is_political", "mean"),
        crime_share=("is_crime", "mean"),
    ).reset_index()
    return grouped


def compute_pri(weekly: pd.DataFrame) -> pd.DataFrame:
    """Compose the four sub-signals, normalise to 0-100."""
    w = weekly.copy()
    # Higher mean_sent = better
    # Higher neg_share / political_share / crime_share = worse, so invert
    w["component_sent"] = w["mean_sent"]
    w["component_neg"] = 1.0 - w["neg_share"].fillna(0.0)
    w["component_pol"] = 1.0 - w["political_share"].fillna(0.0)
    w["component_crime"] = 1.0 - w["crime_share"].fillna(0.0)

    # Min-max normalise each component
    for c in ["component_sent", "component_neg", "component_pol", "component_crime"]:
        col = w[c]
        rng = col.max() - col.min()
        w[c + "_n"] = (col - col.min()) / (rng if rng else 1)

    w["pri_raw"] = (
        0.40 * w["component_sent_n"]
        + 0.30 * w["component_neg_n"]
        + 0.20 * w["component_pol_n"]
        + 0.10 * w["component_crime_n"]
    )
    w["pri"] = w["pri_raw"] * 100.0
    return w[["week", "n", "mean_sent", "neg_share", "political_share", "crime_share", "pri"]]


def annotate_events(weekly: pd.DataFrame) -> pd.DataFrame:
    """Tag the closest week to each known event for chart annotations."""
    w = weekly.copy()
    w["event"] = None
    for d, label in ELECTION_DATES:
        d = pd.to_datetime(d)
        idx = (w["week"] - d).abs().idxmin()
        w.loc[idx, "event"] = label
    return w


def run() -> pd.DataFrame:
    df, _ = load_inputs()
    weekly = weekly_aggregate(df)
    pri = compute_pri(weekly)
    pri = annotate_events(pri)
    pri.to_csv(PRI_CSV, index=False)
    log.info("saved weekly PRI with %d rows to %s", len(pri), PRI_CSV)
    return pri


if __name__ == "__main__":
    run()
