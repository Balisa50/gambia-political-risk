"""
Topic modelling: LDA on TF-IDF + K-Means on sentence embeddings.

The two methods are compared in notebook 06. LDA gives interpretable
topic-word distributions; K-Means on dense embeddings gives semantically
tighter clusters but no human-readable summary. Used together they
cross-validate each other.
"""

from __future__ import annotations

import logging
import pickle

import numpy as np
import pandas as pd

from .config import FEATURES_PKL, TOPICS_CSV

log = logging.getLogger(__name__)


# ── LDA ───────────────────────────────────────────────────────────────


def fit_lda(tfidf, n_topics: int, random_state: int = 42):
    """
    Why LatentDirichletAllocation (sklearn) instead of gensim:
        Simpler API, reproducible with random_state, and TF-IDF input
        is acceptable per the LDA literature when you want term-importance
        weighting. Coherence is computed on the held-out tokens via gensim
        for evaluation.
    """
    from sklearn.decomposition import LatentDirichletAllocation

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=random_state,
        learning_method="online",
        max_iter=20,
    )
    lda.fit(tfidf)
    return lda


def top_words_per_topic(lda, feature_names: list[str], n_words: int = 15) -> list[list[str]]:
    out = []
    for topic_vec in lda.components_:
        idx = topic_vec.argsort()[::-1][:n_words]
        out.append([feature_names[i] for i in idx])
    return out


def coherence_cv(tokens_per_doc: list[list[str]], top_words: list[list[str]]) -> float:
    """c_v coherence using gensim, the standard topic-model evaluation."""
    from gensim.corpora import Dictionary
    from gensim.models.coherencemodel import CoherenceModel

    dictionary = Dictionary(tokens_per_doc)
    cm = CoherenceModel(topics=top_words, texts=tokens_per_doc, dictionary=dictionary, coherence="c_v")
    return cm.get_coherence()


# ── K-Means on embeddings ─────────────────────────────────────────────


def fit_kmeans(embeddings: np.ndarray, k: int, random_state: int = 42):
    """
    Why K-Means (not DBSCAN) on the embeddings:
        News articles cluster into a small number of broad topical buckets
        with no clean density gap between them. DBSCAN's eps/min_samples
        tuning is brittle for high-dim embeddings. K-Means with silhouette
        sweep picks a stable k.
    """
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    km.fit(embeddings)
    return km


def silhouette(embeddings: np.ndarray, labels: np.ndarray) -> float:
    from sklearn.metrics import silhouette_score

    if len(set(labels)) < 2:
        return -1.0
    return float(silhouette_score(embeddings, labels))


# ── Runner ────────────────────────────────────────────────────────────


def run(k_lda: int = 10, k_km: int = 10) -> pd.DataFrame:
    with open(FEATURES_PKL, "rb") as f:
        bundle = pickle.load(f)

    log.info("fitting LDA k=%d", k_lda)
    lda = fit_lda(bundle.tfidf, n_topics=k_lda)
    feat_names = bundle.tfidf_vectorizer.get_feature_names_out().tolist()
    top_words = top_words_per_topic(lda, feat_names, n_words=15)
    log.info("top words per topic:")
    for i, ws in enumerate(top_words):
        log.info("  topic %d: %s", i, ", ".join(ws))

    lda_labels = lda.transform(bundle.tfidf).argmax(axis=1)

    log.info("fitting K-Means k=%d", k_km)
    km = fit_kmeans(bundle.embeddings, k=k_km)
    sil = silhouette(bundle.embeddings, km.labels_)
    log.info("silhouette = %.3f", sil)

    out = pd.DataFrame({
        "url": bundle.df["url"],
        "date": bundle.df["date"],
        "lda_topic": lda_labels,
        "km_cluster": km.labels_,
    })
    out.to_csv(TOPICS_CSV, index=False)
    log.info("saved topic assignments to %s", TOPICS_CSV)
    return out


if __name__ == "__main__":
    run()
