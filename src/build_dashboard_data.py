"""
Assemble a single dashboard.json the Next.js frontend can load directly.

Joins sentiment + topics + cleaned articles, recovers top words per
K-Means cluster (semantic clusters from sentence-transformer embeddings
are far more interpretable than LDA on a 391-article corpus), and emits
a rich payload covering weekly PRI, component sub-signals, per-source
breakdowns, topic summaries with representative headlines, and
most-positive / most-negative examples.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import (
    CLEAN_CSV,
    FEATURES_PKL,
    PRI_CSV,
    SENTIMENT_CSV,
    TOPICS_CSV,
)
from .features import FeatureBundle  # noqa: F401  needed for pickle.load

OUT_PATH = Path("dashboard/public/data/dashboard.json")
N_CLUSTERS = 8

# Hand-curated cluster labels keyed on dominant terms — see notebook output
HUMAN_LABELS: dict[frozenset, str] = {
    frozenset({"bank", "cost", "economic", "financial"}): "Economy & finance",
    frozenset({"jammeh", "government", "crime"}): "Governance & Jammeh era",
    frozenset({"community", "life", "mr"}): "Community & society",
    frozenset({"business", "farmer", "health"}): "Health, business & agriculture",
    frozenset({"barrow", "election", "national"}): "Elections & national politics",
    frozenset({"cup", "football", "game", "match"}): "Sports",
    frozenset({"african", "child", "medium", "people"}): "Africa & media",
    frozenset({"accused", "case", "court", "evidence", "justice"}): "Courts & justice",
}


def _label_cluster(top_terms: list[str]) -> str:
    term_set = set(top_terms)
    best_label, best_score = None, 0
    for key, label in HUMAN_LABELS.items():
        score = len(key & term_set)
        if score > best_score:
            best_score, best_label = score, label
    if best_label:
        return best_label
    return " · ".join(top_terms[:2])


def main() -> None:
    clean = pd.read_csv(CLEAN_CSV, parse_dates=["date"])
    sent = pd.read_csv(SENTIMENT_CSV, parse_dates=["date"])
    topics = pd.read_csv(TOPICS_CSV, parse_dates=["date"])
    pri = pd.read_csv(PRI_CSV, parse_dates=["week"])

    df = clean.merge(sent.drop(columns=["date", "source"], errors="ignore"), on="url", how="inner")
    df = df.merge(topics.drop(columns=["date"], errors="ignore"), on="url", how="inner")

    df["sent_score"] = df["score_db"].where(df["label_db"].notna(), df["vader_text_compound"])
    df["sent_label"] = df["label_db"].fillna(df["vader_text_label"]).str.lower()

    # ── Re-cluster on sentence embeddings ──────────────────────────────
    with open(FEATURES_PKL, "rb") as f:
        bundle = pickle.load(f)
    km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    cluster_labels = km.fit_predict(bundle.embeddings)
    cluster_df = bundle.df[["url"]].copy()
    cluster_df["cluster"] = cluster_labels
    df = df.merge(cluster_df, on="url", how="left")

    # ── Top terms per cluster via TF-IDF on cluster members ────────────
    cluster_top_terms: dict[int, list[str]] = {}
    for k in range(N_CLUSTERS):
        sub = df[df["cluster"] == k]
        if sub.empty:
            cluster_top_terms[k] = []
            continue
        try:
            vec = TfidfVectorizer(max_features=20, ngram_range=(1, 2), stop_words="english")
            vec.fit(sub["tokens_str"].fillna(""))
            cluster_top_terms[k] = vec.get_feature_names_out().tolist()[:8]
        except ValueError:
            cluster_top_terms[k] = []

    # ── Topic summaries ────────────────────────────────────────────────
    topic_summaries = []
    for k in range(N_CLUSTERS):
        sub = df[df["cluster"] == k]
        if sub.empty:
            continue
        sample = sub.sort_values("sent_score", ascending=False).head(2)
        sample_low = sub.sort_values("sent_score").head(1)
        topic_summaries.append({
            "id": int(k),
            "label": _label_cluster(cluster_top_terms[k]),
            "keywords": cluster_top_terms[k],
            "n_articles": int(len(sub)),
            "mean_sentiment": float(sub["sent_score"].mean()),
            "negative_share": float((sub["sent_label"] == "negative").mean()),
            "positive_share": float((sub["sent_label"] == "positive").mean()),
            "sample_positive": [
                {"headline": str(r["headline"])[:160], "source": r["source"], "url": r["url"]}
                for _, r in sample.iterrows()
            ],
            "sample_negative": [
                {"headline": str(r["headline"])[:160], "source": r["source"], "url": r["url"]}
                for _, r in sample_low.iterrows()
            ],
        })
    topic_summaries.sort(key=lambda t: t["n_articles"], reverse=True)

    # ── Per-source ─────────────────────────────────────────────────────
    per_source = (
        df.groupby("source").agg(
            n_articles=("url", "count"),
            mean_sentiment=("sent_score", "mean"),
            negative_share=("sent_label", lambda s: (s == "negative").mean()),
            positive_share=("sent_label", lambda s: (s == "positive").mean()),
        ).reset_index()
        .sort_values("n_articles", ascending=False)
    )
    sources_list = [
        {
            "source": r["source"],
            "n_articles": int(r["n_articles"]),
            "mean_sentiment": float(r["mean_sentiment"]),
            "negative_share": float(r["negative_share"]),
            "positive_share": float(r["positive_share"]),
        }
        for _, r in per_source.iterrows()
    ]

    sent_counts = df["sent_label"].value_counts().to_dict()
    sentiment_distribution = {
        "positive": int(sent_counts.get("positive", 0)),
        "negative": int(sent_counts.get("negative", 0)),
        "neutral": int(sent_counts.get("neutral", 0)),
    }

    cutoff = df["date"].max() - pd.Timedelta(days=120)
    recent = df[df["date"] >= cutoff]
    if recent.empty:
        recent = df
    most_negative = recent.sort_values("sent_score").head(5)
    most_positive = recent.sort_values("sent_score", ascending=False).head(5)

    def _hl_records(d: pd.DataFrame) -> list[dict]:
        return [
            {
                "headline": str(r["headline"])[:200],
                "source": r["source"],
                "date": pd.to_datetime(r["date"]).strftime("%Y-%m-%d"),
                "url": r["url"],
                "sentiment": float(r["sent_score"]),
            }
            for _, r in d.iterrows()
        ]

    pri_series = [
        {
            "week": pd.to_datetime(r["week"]).strftime("%Y-%m-%d"),
            "pri": float(r["pri"]),
            "n_articles": int(r["n"]),
            "mean_sentiment": float(r["mean_sent"]) if not pd.isna(r["mean_sent"]) else None,
            "negative_share": float(r["neg_share"]) if not pd.isna(r["neg_share"]) else None,
            "political_share": float(r["political_share"]) if not pd.isna(r["political_share"]) else None,
            "crime_share": float(r["crime_share"]) if not pd.isna(r["crime_share"]) else None,
            "event": r["event"] if isinstance(r["event"], str) else None,
        }
        for _, r in pri.iterrows()
    ]

    latest = pri.iloc[-1]
    earliest = pri.iloc[0]
    four_back = pri.iloc[-5] if len(pri) >= 5 else earliest
    summary = {
        "current_pri": float(latest["pri"]),
        "current_week": pd.to_datetime(latest["week"]).strftime("%Y-%m-%d"),
        "delta_4w": float(latest["pri"] - four_back["pri"]),
        "n_articles_total": int(len(df)),
        "n_sources": int(df["source"].nunique()),
        "n_weeks": int(len(pri)),
        "first_week": pd.to_datetime(earliest["week"]).strftime("%Y-%m-%d"),
        "last_week": pd.to_datetime(latest["week"]).strftime("%Y-%m-%d"),
    }

    payload = {
        "summary": summary,
        "pri_series": pri_series,
        "topics": topic_summaries,
        "sources": sources_list,
        "sentiment_distribution": sentiment_distribution,
        "most_positive": _hl_records(most_positive),
        "most_negative": _hl_records(most_negative),
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"wrote {OUT_PATH}")
    print(f"  {summary['n_articles_total']} articles, {summary['n_sources']} sources, {summary['n_weeks']} weeks")
    print(f"  {len(topic_summaries)} topics, {sum(sent_counts.values())} sentiment-scored articles")


if __name__ == "__main__":
    main()
