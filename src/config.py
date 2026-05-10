"""Project-wide configuration, paths, and constants."""

from pathlib import Path

# Paths (relative, no hardcoding)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FEATURES_DIR = DATA_DIR / "features"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = OUTPUTS_DIR / "charts"
EDA_DIR = OUTPUTS_DIR / "eda"

for p in (RAW_DIR, PROCESSED_DIR, FEATURES_DIR, MODELS_DIR, CHARTS_DIR, EDA_DIR):
    p.mkdir(parents=True, exist_ok=True)

# Files
RAW_CSV = RAW_DIR / "gambia_news_raw.csv"
CLEAN_CSV = PROCESSED_DIR / "gambia_news_clean.csv"
FEATURES_PKL = FEATURES_DIR / "article_features.pkl"
SENTIMENT_CSV = FEATURES_DIR / "sentiment_scores.csv"
TOPICS_CSV = FEATURES_DIR / "topic_assignments.csv"
PRI_CSV = OUTPUTS_DIR / "political_risk_index.csv"

# Scraping settings (polite to servers)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
    "(+research project, contact abdouliebalisa904@gmail.com)"
)
REQUEST_TIMEOUT = 20
DELAY_MIN_SECONDS = 1.0
DELAY_MAX_SECONDS = 3.0

# Known Gambian events (for PRI validation + date features)
ELECTION_DATES = [
    ("2016-12-01", "2016 presidential election"),
    ("2017-01-19", "Jammeh exile"),
    ("2020-03-17", "COVID-19 declared"),
    ("2021-12-04", "2021 presidential election"),
    ("2022-04-09", "2022 National Assembly elections"),
]
COVID_PERIOD = ("2020-03-01", "2021-12-31")

# Entity flag keyword sets (case-insensitive substring match)
POLITICAL_KEYWORDS = {
    "government", "president", "parliament", "election", "policy",
    "ministry", "barrow", "jammeh", "national assembly", "ecowas",
    "constitution", "cabinet", "minister", "opposition", "ruling party",
}
ECONOMIC_KEYWORDS = {
    "gdp", "inflation", "currency", "trade", "investment", "dalasi",
    "remittance", "bank", "central bank", "cbg", "imf", "world bank",
    "exchange rate", "tax", "budget", "tourism",
}
CRIME_KEYWORDS = {
    "crime", "arrest", "corruption", "fraud", "robbery", "murder",
    "homicide", "police", "trafficking", "drugs", "violence", "court",
    "trial", "verdict", "convicted", "prison",
}
