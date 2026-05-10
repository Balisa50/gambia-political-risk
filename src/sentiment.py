"""
Sentiment analysis: VADER (lexicon) vs distilBERT (transformer).

Both are evaluated against a manually-labelled 200-article holdout in
notebook 05. The model that wins drives the Political Risk Index.
"""

from __future__ import annotations

import logging

import nltk
import numpy as np
import pandas as pd

from .config import CLEAN_CSV, SENTIMENT_CSV

log = logging.getLogger(__name__)

# Ensure VADER is available
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer  # noqa: F401
except LookupError:
    nltk.download("vader_lexicon", quiet=True)


# ── VADER ─────────────────────────────────────────────────────────────


def vader_scores(texts: list[str]) -> pd.DataFrame:
    """
    Why VADER:
        Lexicon based, instant, no GPU. Tuned on social-media English
        which makes it a fair baseline against a deep model. Its weakness:
        misses sarcasm and any politically-loaded vocabulary it hasn't seen.
    """
    from nltk.sentiment.vader import SentimentIntensityAnalyzer

    sia = SentimentIntensityAnalyzer()
    rows = []
    for t in texts:
        s = sia.polarity_scores(t or "")
        s["label"] = "positive" if s["compound"] >= 0.05 else ("negative" if s["compound"] <= -0.05 else "neutral")
        rows.append(s)
    return pd.DataFrame(rows)


# ── distilBERT (HuggingFace) ─────────────────────────────────────────


def distilbert_scores(
    texts: list[str],
    model_name: str = "distilbert-base-uncased-finetuned-sst-2-english",
    max_length: int = 512,
    batch_size: int = 16,
) -> pd.DataFrame:
    """
    Why distilbert-sst2 (not full BERT):
        - 60% of BERT's parameters, 95% of its accuracy on SST-2
        - Runs on CPU at acceptable speed
        - Pretrained on Stanford Sentiment Treebank, which is sentence-level
          movie reviews. Imperfect for news, but the standard transferable
          baseline. We compare against VADER and pick the winner per task.
    """
    from transformers import pipeline

    pipe = pipeline(
        "sentiment-analysis",
        model=model_name,
        device=-1,  # CPU; switch to 0 if you have a GPU
        truncation=True,
        max_length=max_length,
    )

    out = []
    for i in range(0, len(texts), batch_size):
        batch = [t or "" for t in texts[i : i + batch_size]]
        results = pipe(batch)
        for r in results:
            label = r["label"].lower()  # POSITIVE / NEGATIVE
            out.append({"label_db": label, "score_db": float(r["score"])})
    return pd.DataFrame(out)


# ── Runner ────────────────────────────────────────────────────────────


def run(use_distilbert: bool = True) -> pd.DataFrame:
    df = pd.read_csv(CLEAN_CSV)

    log.info("running VADER on %d articles", len(df))
    v_text = vader_scores(df["text"].fillna("").tolist())
    v_text = v_text.rename(columns=lambda c: f"vader_text_{c}")
    v_head = vader_scores(df["headline"].fillna("").tolist())
    v_head = v_head.rename(columns=lambda c: f"vader_head_{c}")

    out = pd.concat([df[["url", "date", "source"]].reset_index(drop=True), v_text, v_head], axis=1)

    if use_distilbert:
        log.info("running distilBERT on headlines (truncate 512)")
        db = distilbert_scores(df["headline"].fillna("").tolist())
        out = pd.concat([out, db.reset_index(drop=True)], axis=1)

    out.to_csv(SENTIMENT_CSV, index=False)
    log.info("saved sentiment scores to %s", SENTIMENT_CSV)
    return out


if __name__ == "__main__":
    run()
