"""
FastAPI service for the Gambian Political Risk Index.

Three endpoints (matching the project brief but implemented on FastAPI
because the rest of my Python services use FastAPI, not Flask):

    POST /analyze
        Body: {"text": "..."}
        Returns: sentiment label + confidence, predicted topic, risk score

    GET  /risk-index
        Returns the full weekly PRI as a JSON array.

    GET  /risk-index/current
        Returns the most recent week's PRI, the trend vs 4 weeks ago,
        and the top 3 topics driving the current score.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
PRI_CSV = ROOT / "outputs" / "political_risk_index.csv"
FEATURES_PKL = ROOT / "data" / "features" / "article_features.pkl"

app = FastAPI(
    title="Gambia Political Risk API",
    description="Sentiment + topic + weekly PRI for Gambian news.",
    version="0.1.0",
)

# CORS for the Next.js dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lazy model loading ────────────────────────────────────────────────
#
# Heavy models load on first /analyze call instead of at startup so the
# /risk-index endpoints serve fast even on a cold Render instance.

_state: dict = {}


def get_distilbert():
    if "db" not in _state:
        from transformers import pipeline

        _state["db"] = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=-1,
            truncation=True,
            max_length=512,
        )
    return _state["db"]


def get_lda():
    if "lda" not in _state:
        if not FEATURES_PKL.exists():
            return None
        with open(FEATURES_PKL, "rb") as f:
            bundle = pickle.load(f)
        _state["bundle"] = bundle
    return _state.get("lda")  # populated by training step; placeholder here


# ── Request / response schemas ────────────────────────────────────────


class AnalyzeIn(BaseModel):
    text: str


class AnalyzeOut(BaseModel):
    sentiment: str
    confidence: float
    topic: Optional[str] = None
    risk_contribution: float


# ── Endpoints ─────────────────────────────────────────────────────────


@app.get("/")
def health():
    return {"status": "ok", "service": "gambia-political-risk"}


@app.post("/analyze", response_model=AnalyzeOut)
def analyze(payload: AnalyzeIn) -> AnalyzeOut:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    pipe = get_distilbert()
    out = pipe([text])[0]
    label = out["label"].lower()
    score = float(out["score"])

    # Risk contribution: positive sentiment lowers risk; negative raises it.
    # Map [-1,1] sentiment to a 0-100 risk-contribution scale where 50 is neutral.
    signed = score if label == "positive" else -score
    risk = 50.0 - signed * 50.0

    return AnalyzeOut(
        sentiment=label,
        confidence=score,
        topic=None,  # filled in once an LDA classifier is exported
        risk_contribution=round(risk, 2),
    )


@app.get("/risk-index")
def risk_index():
    if not PRI_CSV.exists():
        raise HTTPException(status_code=503, detail="PRI not yet computed; run notebook 07")
    df = pd.read_csv(PRI_CSV, parse_dates=["week"])
    return [
        {
            "date": r.week.isoformat(),
            "score": round(float(r.pri), 2),
            "n_articles": int(r.n),
            "event": r.event if isinstance(r.event, str) else None,
        }
        for r in df.itertuples()
    ]


@app.get("/risk-index/current")
def risk_index_current():
    if not PRI_CSV.exists():
        raise HTTPException(status_code=503, detail="PRI not yet computed; run notebook 07")
    df = pd.read_csv(PRI_CSV, parse_dates=["week"]).sort_values("week")
    if df.empty:
        raise HTTPException(status_code=503, detail="PRI is empty")
    latest = df.iloc[-1]
    four_weeks_ago = df.iloc[-5] if len(df) >= 5 else df.iloc[0]
    delta = float(latest.pri) - float(four_weeks_ago.pri)
    if delta > 2.0:
        trend = "improving"
    elif delta < -2.0:
        trend = "declining"
    else:
        trend = "stable"
    return {
        "date": latest.week.isoformat(),
        "score": round(float(latest.pri), 2),
        "trend": trend,
        "delta_4w": round(delta, 2),
    }
