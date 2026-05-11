"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import { ArrowUpRight, ArrowDownRight, Minus, ExternalLink } from "lucide-react";

interface PriPoint {
  date: string;
  score: number;
  n_articles: number;
  event: string | null;
}

const ELECTION_EVENTS: { date: string; label: string }[] = [
  { date: "2016-12-01", label: "2016 election" },
  { date: "2017-01-19", label: "Jammeh exile" },
  { date: "2020-03-17", label: "COVID-19 declared" },
  { date: "2021-12-04", label: "2021 election" },
  { date: "2022-04-09", label: "2022 NA elections" },
];

export default function HomePage() {
  const [series, setSeries] = useState<PriPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/data/political_risk_index.csv")
      .then((r) => r.text())
      .then((csv) => {
        const lines = csv.trim().split("\n");
        const header = lines[0].split(",");
        const idx = (k: string) => header.indexOf(k);
        const out: PriPoint[] = [];
        for (let i = 1; i < lines.length; i++) {
          const cells = lines[i].split(",");
          out.push({
            date: cells[idx("week")],
            score: parseFloat(cells[idx("pri")]),
            n_articles: parseInt(cells[idx("n")], 10),
            event: cells[idx("event")] || null,
          });
        }
        out.sort((a, b) => a.date.localeCompare(b.date));
        setSeries(out);
      })
      .catch(() => setSeries([]))
      .finally(() => setLoading(false));
  }, []);

  const latest = series.at(-1);
  const fourBack = series.length >= 5 ? series[series.length - 5] : series[0];
  const delta = latest && fourBack ? latest.score - fourBack.score : 0;
  const trend = delta > 2 ? "improving" : delta < -2 ? "declining" : "stable";
  const TrendIcon = trend === "improving" ? ArrowUpRight : trend === "declining" ? ArrowDownRight : Minus;
  const trendColor = trend === "improving" ? "text-emerald-400" : trend === "declining" ? "text-rose-400" : "text-white/55";

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-10">
        <p className="font-mono text-xs uppercase tracking-[0.32em] text-accent/85">~/gambia/political-risk-index</p>
        <h1 className="mt-3 text-balance text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-tight">
          The Gambia Political Risk Index
        </h1>
        <p className="mt-3 max-w-2xl text-pretty text-base leading-relaxed text-white/60">
          A weekly 0-100 score derived from sentiment, topic prevalence, and crime coverage across multiple Gambian news publications. Higher means a more stable, positive news environment. Built end-to-end from a custom scraping pipeline, TF-IDF + sentence-transformer embeddings, VADER + distilBERT sentiment, LDA + K-Means topic models, and a weighted composite index.
        </p>
        <p className="mt-3 text-xs text-white/45">
          Sources: The Point · Foroyaa · Standard · Kaironews · The Voice · Alkamba Times ·{" "}
          <a href="https://github.com/Balisa50/gambia-political-risk" target="_blank" rel="noreferrer noopener" className="underline-offset-2 hover:text-accent hover:underline">
            source on GitHub
            <ExternalLink className="ml-0.5 inline h-3 w-3" />
          </a>
        </p>
      </header>

      {/* Current */}
      <section className="mb-10 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-accent/30 bg-accent/[0.03] p-5">
          <p className="font-mono text-[10px] uppercase tracking-wider text-accent/85">Current PRI</p>
          <p className="mt-2 text-4xl font-semibold tabular-nums">{latest ? latest.score.toFixed(1) : "-"}</p>
          {latest && fourBack && (
            <p className={`mt-2 inline-flex items-center gap-1 text-xs ${trendColor}`}>
              <TrendIcon className="h-3.5 w-3.5" /> {trend} ({delta >= 0 ? "+" : ""}
              {delta.toFixed(1)} vs 4 wks ago)
            </p>
          )}
        </div>
        <Stat label="Articles in latest week" value={latest?.n_articles?.toLocaleString() ?? "-"} />
        <Stat label="Weeks observed" value={series.length.toLocaleString()} />
      </section>

      {/* Chart */}
      <section className="rounded-2xl border border-white/10 bg-surface p-5 md:p-7">
        <h2 className="mb-4 text-lg font-medium">Weekly PRI</h2>
        {loading ? (
          <p className="text-white/45">Loading…</p>
        ) : series.length === 0 ? (
          <p className="text-white/45">No data available.</p>
        ) : (
          <div className="h-96 w-full">
            <ResponsiveContainer>
              <LineChart data={series.map((p) => ({ ...p, ts: new Date(p.date).getTime() }))}>
                <CartesianGrid stroke="#1a1d24" strokeDasharray="3 3" />
                <XAxis
                  dataKey="ts"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
                  stroke="#888"
                />
                <YAxis domain={[0, 100]} stroke="#888" />
                <Tooltip
                  contentStyle={{ background: "#0b0d12", border: "1px solid #1a1d24" }}
                  labelFormatter={(v) => new Date(v as number).toLocaleDateString()}
                  formatter={(value: number) => [value.toFixed(1), "PRI"]}
                />
                <Line type="monotone" dataKey="score" stroke="#00f0ff" strokeWidth={2} dot={{ r: 2.5 }} />
                {ELECTION_EVENTS.filter((e) => {
                  if (series.length === 0) return false;
                  const t = new Date(e.date).getTime();
                  return t >= new Date(series[0].date).getTime() && t <= new Date(series[series.length - 1].date).getTime();
                }).map((e) => (
                  <ReferenceLine
                    key={e.date}
                    x={new Date(e.date).getTime()}
                    stroke="#ff5577"
                    strokeDasharray="2 4"
                    label={{ value: e.label, fill: "#ff5577", fontSize: 10, position: "top" }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      {/* Methodology */}
      <section className="mt-10 rounded-2xl border border-white/10 bg-surface p-5 md:p-7">
        <h2 className="mb-4 text-lg font-medium">How the index is built</h2>
        <ol className="ml-5 list-decimal space-y-3 text-sm leading-relaxed text-white/70">
          <li>
            <strong className="text-white/90">Scrape</strong> articles politely from Gambian publications, 1-3 second random delays, graceful per-page failure
          </li>
          <li>
            <strong className="text-white/90">Preprocess</strong> with NLTK: lowercase, strip HTML/URLs, tokenise, lemmatise (WordNet), drop stopwords, dedupe by URL and headline
          </li>
          <li>
            <strong className="text-white/90">Feature engineer</strong>: TF-IDF (10000 features, bigrams), sentence-transformer embeddings (all-MiniLM-L6-v2), political/economic/crime topic flags, date features
          </li>
          <li>
            <strong className="text-white/90">Sentiment</strong>: VADER (lexicon baseline) vs distilBERT-SST2 (transformer), evaluated against manually-labelled holdout
          </li>
          <li>
            <strong className="text-white/90">Topics</strong>: LDA on TF-IDF for interpretability + K-Means on embeddings for tightness, cross-validated against each other
          </li>
          <li>
            <strong className="text-white/90">Composite PRI</strong>: 40% mean sentiment, 30% (1 - negative share), 20% (1 - political prevalence), 10% (1 - crime prevalence), min-max normalised
          </li>
          <li>
            <strong className="text-white/90">Validate</strong>: chart annotated with known Gambian events, Pearson correlation against World Bank GDP growth and remittance inflows
          </li>
        </ol>
      </section>

      <footer className="mt-12 text-center text-xs text-white/35">
        Built by Abdoulie Balisa.{" "}
        <a href="https://balisa50.github.io" target="_blank" rel="noreferrer noopener" className="underline-offset-2 hover:text-accent hover:underline">
          portfolio
        </a>{" "}
        ·{" "}
        <a href="https://github.com/Balisa50/gambia-political-risk" target="_blank" rel="noreferrer noopener" className="underline-offset-2 hover:text-accent hover:underline">
          source
        </a>
      </footer>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-surface p-5">
      <p className="font-mono text-[10px] uppercase tracking-wider text-white/45">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
