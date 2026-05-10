"""Generate the 9 notebook scaffolds. Run once."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notebooks"
OUT.mkdir(exist_ok=True)


def nb(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text}


SPECS = [
    (
        "01_data_collection.ipynb",
        [
            md(
                "# 01, Data collection\n\n"
                "Scrape four Gambian news publications into a single CSV. Polite rate "
                "limiting (1-3s random delay), graceful per-page failure, target 5000+ articles.\n\n"
                "**Sources**\n"
                "- The Point Newspaper\n- Foroyaa\n- Gainako\n- Standard Newspaper\n\n"
                "**Why BeautifulSoup not Scrapy?** Scrapy is overkill for four sites and adds a heavy "
                "framework dependency. BeautifulSoup + requests is enough and easier to read."
            ),
            code(
                "from src.scraper import scrape_all\n"
                "import pandas as pd\n\n"
                "df = scrape_all(max_articles_per_source=2000)\n"
                "print(f'collected {len(df)} articles')\n"
                "df.head()"
            ),
            md("## Distribution by source and date"),
            code("df['source'].value_counts()"),
            code(
                "df['date'] = pd.to_datetime(df['date'], errors='coerce')\n"
                "print('date range:', df['date'].min(), 'to', df['date'].max())"
            ),
        ],
    ),
    (
        "02_preprocessing.ipynb",
        [
            md(
                "# 02, Preprocessing\n\n"
                "Lowercase, strip HTML/URLs/emails/non-text characters, tokenise, remove stopwords, "
                "lemmatise (WordNet), drop short tokens, drop empty rows, de-duplicate.\n\n"
                "**Why apostrophes are kept**: English contractions ('dont', 'isnt') lose meaning if "
                "apostrophes are dropped before lemmatisation."
            ),
            code(
                "from src.preprocessor import run\n"
                "df = run()\n"
                "print(f'cleaned dataset: {len(df)} rows')"
            ),
            code(
                "print(df['source'].value_counts())\n"
                "print()\n"
                "print('date range:', df['date'].min(), 'to', df['date'].max())"
            ),
        ],
    ),
    (
        "03_eda.ipynb",
        [
            md(
                "# 03, Exploratory data analysis\n\n"
                "Visualise the corpus before any modelling. All outputs save to `outputs/eda/`."
            ),
            code(
                "import pandas as pd\n"
                "import matplotlib.pyplot as plt\n"
                "from src.config import CLEAN_CSV, EDA_DIR\n\n"
                "df = pd.read_csv(CLEAN_CSV, parse_dates=['date'])\n"
                "print(len(df), 'articles')"
            ),
            md("## Article volume over time"),
            code(
                "monthly = df.set_index('date').resample('MS').size()\n"
                "fig, ax = plt.subplots(figsize=(11, 4))\n"
                "monthly.plot(ax=ax, color='#00f0ff')\n"
                "ax.set_title('Articles per month'); ax.set_ylabel('count')\n"
                "plt.tight_layout(); plt.savefig(EDA_DIR / 'monthly_volume.png'); plt.show()"
            ),
            md("## Top 50 most frequent words"),
            code(
                "from collections import Counter\n"
                "words = Counter()\n"
                "for toks in df['tokens_str'].fillna('').str.split():\n"
                "    words.update(toks)\n"
                "top = pd.Series(dict(words.most_common(50))).sort_values()\n"
                "top.tail(50).plot.barh(figsize=(8, 12)); plt.title('Top 50 words')\n"
                "plt.tight_layout(); plt.savefig(EDA_DIR / 'top_words.png'); plt.show()"
            ),
            md(
                "## Named entity recognition (spaCy)\n\n"
                "Extract PERSON / ORG / GPE entities. Reveals which actors dominate the news cycle."
            ),
            code(
                "# import spacy\n"
                "# nlp = spacy.load('en_core_web_sm')\n"
                "# sample = df.sample(min(200, len(df)), random_state=42)\n"
                "# ents = []\n"
                "# for txt in sample['text'].fillna(''):\n"
                "#     doc = nlp(txt[:5000])\n"
                "#     for ent in doc.ents:\n"
                "#         ents.append((ent.label_, ent.text))\n"
                "# pd.DataFrame(ents, columns=['label', 'text']).groupby('label')['text'].apply(\n"
                "#     lambda s: s.value_counts().head(10))"
            ),
        ],
    ),
    (
        "04_feature_engineering.ipynb",
        [
            md(
                "# 04, Feature engineering\n\n"
                "Build TF-IDF + sentence embeddings + article-level numeric features + topic flags + "
                "date features. Saves a single pickle for downstream notebooks."
            ),
            code(
                "from src.features import run\n"
                "bundle = run(skip_embeddings=False)\n"
                "print('TF-IDF shape:', bundle.tfidf.shape)\n"
                "print('embeddings shape:', bundle.embeddings.shape)\n"
                "print('article-level features:', bundle.article_features.columns.tolist())"
            ),
        ],
    ),
    (
        "05_sentiment_analysis.ipynb",
        [
            md(
                "# 05, Sentiment analysis\n\n"
                "Compare VADER (lexicon baseline) against distilBERT-SST2. Evaluate against 200 "
                "manually-labelled articles. The winner drives the PRI."
            ),
            code(
                "from src.sentiment import run\n"
                "out = run(use_distilbert=True)\n"
                "out.head()"
            ),
            md(
                "## Manual evaluation\n\n"
                "Label 200 random articles by hand. The cell below saves a CSV template for you to fill in."
            ),
            code(
                "import pandas as pd\n"
                "from src.config import CLEAN_CSV\n\n"
                "df = pd.read_csv(CLEAN_CSV)\n"
                "sample = df.sample(200, random_state=42)[['url', 'headline', 'text']]\n"
                "sample['manual_label'] = ''\n"
                "sample.to_csv('data/features/manual_labels_template.csv', index=False)\n"
                "print('template saved. Fill manual_label with positive/negative/neutral.')"
            ),
            md("## Compare against manual labels (run after labelling)"),
            code(
                "# from sklearn.metrics import classification_report, confusion_matrix\n"
                "# manual = pd.read_csv('data/features/manual_labels_filled.csv')\n"
                "# scores = pd.read_csv('data/features/sentiment_scores.csv')\n"
                "# m = manual.merge(scores, on='url', how='inner')\n"
                "# print('VADER report:')\n"
                "# print(classification_report(m['manual_label'], m['vader_text_label']))\n"
                "# m_bin = m[m['manual_label'].isin(['positive', 'negative'])]\n"
                "# print('distilBERT report:')\n"
                "# print(classification_report(m_bin['manual_label'], m_bin['label_db']))"
            ),
        ],
    ),
    (
        "06_topic_modeling.ipynb",
        [
            md(
                "# 06, Topic modelling\n\n"
                "LDA on TF-IDF (interpretable) + K-Means on sentence embeddings (semantically tight). "
                "**Why two methods?** They cross-validate each other."
            ),
            code(
                "from src.topics import run\n"
                "out = run(k_lda=10, k_km=10)\n"
                "out.head()"
            ),
            md("## Coherence sweep for LDA k"),
            code(
                "# from src.topics import fit_lda, top_words_per_topic, coherence_cv\n"
                "# import pickle\n"
                "# from src.config import FEATURES_PKL\n"
                "# bundle = pickle.load(open(FEATURES_PKL, 'rb'))\n"
                "# tokens_per_doc = bundle.df['tokens_str'].fillna('').str.split().tolist()\n"
                "# feat_names = bundle.tfidf_vectorizer.get_feature_names_out().tolist()\n"
                "# scores = {}\n"
                "# for k in [5, 8, 10, 15]:\n"
                "#     lda = fit_lda(bundle.tfidf, n_topics=k)\n"
                "#     tw = top_words_per_topic(lda, feat_names)\n"
                "#     scores[k] = coherence_cv(tokens_per_doc, tw)\n"
                "# print(scores)"
            ),
            md("## UMAP visualisation"),
            code(
                "# import umap, matplotlib.pyplot as plt, pickle\n"
                "# from src.config import FEATURES_PKL\n"
                "# bundle = pickle.load(open(FEATURES_PKL, 'rb'))\n"
                "# u = umap.UMAP(n_components=2, random_state=42).fit_transform(bundle.embeddings)\n"
                "# plt.scatter(u[:,0], u[:,1], s=4, alpha=0.6)\n"
                "# plt.title('K-Means clusters in UMAP space'); plt.show()"
            ),
        ],
    ),
    (
        "07_political_risk_index.ipynb",
        [
            md(
                "# 07, Political Risk Index\n\n"
                "Aggregate signals weekly, combine into 0-100 score.\n\n"
                "**Weights** (40% mean sentiment, 30% 1-neg share, 20% 1-political prev, 10% 1-crime prev)\n\n"
                "Validation: known event annotations + Pearson correlation against GDP and remittances."
            ),
            code(
                "from src.risk_index import run\n"
                "pri = run()\n"
                "pri.tail(10)"
            ),
            md("## Plot with event annotations"),
            code(
                "import matplotlib.pyplot as plt\n"
                "import pandas as pd\n"
                "from src.config import CHARTS_DIR, ELECTION_DATES, PRI_CSV\n\n"
                "pri = pd.read_csv(PRI_CSV, parse_dates=['week'])\n"
                "fig, ax = plt.subplots(figsize=(13, 5))\n"
                "ax.plot(pri['week'], pri['pri'], color='#00f0ff', lw=1.5)\n"
                "for d, label in ELECTION_DATES:\n"
                "    ax.axvline(pd.to_datetime(d), color='#ff5577', linestyle='--', alpha=0.6)\n"
                "    ax.text(pd.to_datetime(d), 95, label, rotation=90, fontsize=8, color='#ff5577')\n"
                "ax.set_title('Gambia Political Risk Index, weekly')\n"
                "ax.set_ylabel('PRI (0-100)'); ax.set_ylim(0, 100)\n"
                "plt.tight_layout(); plt.savefig(CHARTS_DIR / 'political_risk_index.png'); plt.show()"
            ),
            md("## Correlation with macro indicators"),
            code(
                "# import wbdata, datetime\n"
                "# gdp = wbdata.get_dataframe({'NY.GDP.MKTP.KD.ZG': 'gdp_growth'}, country='GMB',\n"
                "#     date=(datetime.datetime(2016,1,1), datetime.datetime(2025,12,31)))\n"
                "# remit = wbdata.get_dataframe({'BX.TRF.PWKR.CD.DT': 'remittances'}, country='GMB',\n"
                "#     date=(datetime.datetime(2016,1,1), datetime.datetime(2025,12,31)))\n"
                "# pri['year'] = pri['week'].dt.year\n"
                "# annual = pri.groupby('year')['pri'].mean()\n"
                "# from scipy.stats import pearsonr\n"
                "# r, p = pearsonr(annual, gdp['gdp_growth'])\n"
                "# print(f'PRI vs GDP growth: r={r:.3f}, p={p:.4f}')"
            ),
        ],
    ),
    (
        "08_evaluation.ipynb",
        [
            md(
                "# 08, Evaluation summary\n\n"
                "Tables that compare every modelling decision: VADER vs distilBERT, LDA k sweep, "
                "PRI event matches, correlation analysis. Plain-English interpretation."
            ),
            code(
                "# This notebook reads the artefacts from 05/06/07 and renders the\n"
                "# summary tables that go in the README."
            ),
        ],
    ),
    (
        "09_shap_interpretation.ipynb",
        [
            md(
                "# 09, SHAP interpretation\n\n"
                "Top 20 features driving sentiment classification. Force plots for one clearly positive, "
                "one clearly negative, one ambiguous article.\n\n"
                "**Why SHAP not LIME?** Shapley values are mathematically more principled for additive "
                "feature attribution. SHAP has a TextExplainer specifically for transformer pipelines."
            ),
            code(
                "# import shap\n"
                "# from transformers import pipeline\n"
                "# pipe = pipeline('sentiment-analysis',\n"
                "#     model='distilbert-base-uncased-finetuned-sst-2-english')\n"
                "# explainer = shap.Explainer(pipe)\n"
                "# samples = ['<positive headline>', '<negative headline>', '<ambiguous>']\n"
                "# shap_values = explainer(samples)\n"
                "# shap.plots.text(shap_values[0])"
            ),
        ],
    ),
]


for fname, cells in SPECS:
    path = OUT / fname
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb(cells), f, indent=1, ensure_ascii=False)
    print(f"wrote {path}")


print(f"\nTotal: {len(SPECS)} notebooks")
