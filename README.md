# Gambia News Sentiment Analyzer & Political Risk Index

End-to-end NLP pipeline that scrapes Gambian news, runs sentiment + topic analysis, and produces a weekly Political Risk Index (PRI) for The Gambia. Every step is documented, every technical choice is justified.

**Live demo**: Dashboard on Vercel · API on Render
**Data sources**: The Point Newspaper, Foroyaa, Gainako, Standard Newspaper

## Why this exists

The Gambia has no public-facing political risk index. International indices (Moody's, Economist Intelligence Unit, Fitch) cover the country annually with proprietary methodology and a paywall. Citizens, diaspora investors, and small businesses making decisions about risk in The Gambia have nothing they can read in real time. This project builds a transparent, weekly, public PRI grounded in actual Gambian news coverage. Anyone can audit the methodology.

## Pipeline

```
news scrape → preprocessing → features → sentiment + topics → weekly PRI → API + dashboard
```

### 1. Data collection (`src/scraper.py`)
- BeautifulSoup + requests
- 4 sources, polite rate limiting (1-3s random delays), graceful failure per page
- Target 5,000+ articles across all sources
- Output: `data/raw/gambia_news_raw.csv`

### 2. Preprocessing (`src/preprocessor.py`)
- Lowercase, strip HTML / URLs / emails / non-text characters
- NLTK tokenisation, English stopword removal, WordNet lemmatisation
- Drop empty / short articles, de-duplicate by URL and headline
- Output: `data/processed/gambia_news_clean.csv`

### 3. Feature engineering (`src/features.py`)
- **TF-IDF** (10k features, bigrams, min_df=3, max_df=0.85)
- **Sentence embeddings** via `sentence-transformers/all-MiniLM-L6-v2`
- **Article-level**: word/sentence count, lexical diversity, NER count
- **Topic flags**: political / economic / crime via curated keyword sets
- **Date features**: day/month/quarter/year, days from nearest election, COVID period flag
- Output: `data/features/article_features.pkl`

### 4. Sentiment (`src/sentiment.py`, notebook 05)
- **VADER** (NLTK lexicon, baseline) — applied to headline and body separately
- **distilBERT-SST2** — applied to headlines (truncated 512 tokens)
- Manual labelling of 200 random articles for evaluation
- Compare on accuracy, precision, recall, F1, AUC; pick the winner
- Output: `data/features/sentiment_scores.csv`

### 5. Topics (`src/topics.py`, notebook 06)
- **LDA** on TF-IDF, k ∈ {5, 8, 10, 15}, optimal selected by `c_v` coherence
- **K-Means** on sentence embeddings, k ∈ {5..15}, optimal by silhouette
- UMAP 2D visualisation of clusters; cross-validate LDA topics against K-Means clusters
- Manual labels per LDA topic (Politics, Economy, Health, Sports, Crime, Development, International)
- Output: `data/features/topic_assignments.csv`

### 6. Political Risk Index (`src/risk_index.py`, notebook 07)
Weekly aggregate, weighted composite:

| Component | Weight |
| --- | --- |
| Mean sentiment (distilBERT) | 40% |
| 1 − negative-article share | 30% |
| 1 − political-topic prevalence | 20% |
| 1 − crime prevalence | 10% |

Min-max normalised to 0-100. Validated against:
- Known Gambian events (2016 election, Jammeh exile, COVID-19, 2021 election)
- Pearson correlation with World Bank GDP growth
- Pearson correlation with remittance inflows

Output: `outputs/political_risk_index.csv` + annotated chart.

### 7. SHAP interpretation (notebook 09)
Top 20 features driving sentiment classification, force plots for 3 example articles, plain-English narrative of what the model has learned about Gambian political vocabulary.

### 8. API (`api/main.py`, FastAPI)
- `POST /analyze` — sentiment + topic + risk-contribution for any text
- `GET /risk-index` — full weekly PRI as JSON
- `GET /risk-index/current` — latest week, trend vs 4 weeks ago

### 9. Dashboard (`dashboard/`, Next.js 16 + Recharts)
- Page 1 — PRI line chart with event annotations + current score
- Page 2 — Analyse-text box
- Page 3 — Topic explorer
- Page 4 — Data overview

## Why these choices

| Choice | Why this, not the alternative |
| --- | --- |
| **TF-IDF, not bag-of-words** | TF-IDF down-weights common newsroom filler ("said", "according") so rare topical terms carry the signal. |
| **all-MiniLM-L6-v2, not mpnet-base** | 95% of mpnet's quality at a third of the inference cost. Important on a laptop. |
| **distilBERT, not full BERT** | 60% of the parameters, 95% of accuracy, runs on CPU. |
| **LDA + K-Means, not just one** | LDA gives interpretable topic-word distributions; K-Means on embeddings gives semantically tighter clusters. Cross-validating both catches errors either alone would miss. |
| **K-Means, not DBSCAN** | News articles cluster into broad buckets with no clean density gap. DBSCAN's eps tuning is brittle for high-dim embeddings. |
| **FastAPI, not Flask** | Native async + type validation via Pydantic. Same stack used in my other Python services. |
| **Next.js + Recharts dashboard, not Streamlit** | Production-grade UI, deployable on Vercel free tier, matches the rest of my portfolio's design language. |
| **Render for backend, Vercel for frontend** | Free tier on both, separation of concerns. |

## Running locally

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Run the pipeline (each notebook in order)
jupyter notebook notebooks/

# Or run modules directly
python -m src.scraper          # scrape
python -m src.preprocessor     # clean
python -m src.features         # build features
python -m src.sentiment        # sentiment scores
python -m src.topics           # topics
python -m src.risk_index       # weekly PRI

# API
uvicorn api.main:app --reload

# Dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

## Project layout

```
gambia-news-sentiment/
  data/{raw,processed,features}/
  notebooks/                 9 Jupyter notebooks, one per pipeline step
  src/                       config, scraper, preprocessor, features, sentiment, topics, risk_index
  api/                       FastAPI service
  dashboard/                 Next.js + Recharts dashboard
  outputs/{charts,eda}/      generated plots, PRI csv
  requirements.txt
  render.yaml                Render deploy spec for the API
```

## Limitations

- Coverage skewed toward English-language sources. Wolof, Mandinka, Fula print is not in the corpus.
- Sentiment labels (positive/negative/neutral) are evaluated against my own 200-article manual sample. A larger labelling effort is needed for a publishable accuracy claim.
- distilBERT-SST2 was trained on movie reviews. It transfers reasonably but a fine-tune on Gambian political language would improve precision.
- The PRI is one signal among many. It does not replace structured economic indicators or formal political risk assessments — it complements them.

## What's next

- Fine-tune sentiment on a Gambian-labelled corpus (with a real labelling team)
- Add Wolof / Mandinka source ingestion via translation pipeline
- Daily cadence (currently weekly) once the data refresh cron is on a paid tier
- Compare PRI against EIU / Fitch annual ratings as ground truth for the long-term signal

## References

- VADER: Hutto & Gilbert 2014, "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text"
- distilBERT: Sanh et al. 2019
- LDA: Blei, Ng, Jordan 2003
- UMAP: McInnes, Healy, Melville 2018
- World Bank Gambia indicators: data.worldbank.org
- KNOMAD bilateral remittance matrix: knomad.org
