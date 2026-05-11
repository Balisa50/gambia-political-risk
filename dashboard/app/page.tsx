"use client";

import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
  BarChart, Bar, Cell, PieChart, Pie,
} from "recharts";
import { ArrowUpRight, ArrowDownRight, Minus, ExternalLink, Newspaper, Tag, ThumbsUp, ThumbsDown } from "lucide-react";

interface Headline { headline: string; source: string; url: string; date?: string; sentiment?: number; }
interface Topic {
  id: number; label: string; keywords: string[]; n_articles: number;
  mean_sentiment: number; negative_share: number; positive_share: number;
  sample_positive: Headline[]; sample_negative: Headline[];
}
interface Source {
  source: string; n_articles: number; mean_sentiment: number;
  negative_share: number; positive_share: number;
}
interface PriPoint {
  week: string; pri: number; n_articles: number;
  mean_sentiment: number | null; negative_share: number | null;
  political_share: number | null; crime_share: number | null;
  event: string | null;
}
interface Dashboard {
  summary: {
    current_pri: number; current_week: string; delta_4w: number;
    n_articles_total: number; n_sources: number; n_weeks: number;
    first_week: string; last_week: string;
  };
  pri_series: PriPoint[];
  topics: Topic[];
  sources: Source[];
  sentiment_distribution: { positive: number; negative: number; neutral: number };
  most_positive: Headline[];
  most_negative: Headline[];
}

const ELECTION_EVENTS = [
  { date: "2016-12-01", label: "2016 election" },
  { date: "2017-01-19", label: "Jammeh exile" },
  { date: "2020-03-17", label: "COVID-19 declared" },
  { date: "2021-12-04", label: "2021 election" },
  { date: "2022-04-09", label: "2022 NA elections" },
];

const SENTIMENT_COLORS = { positive: "#34d399", negative: "#fb7185", neutral: "#94a3b8" };

export default function HomePage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => r.json())
      .then((d) => setData(d as Dashboard))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  const trend = useMemo(() => {
    if (!data) return { dir: "stable", icon: Minus, color: "text-white/55" };
    const d = data.summary.delta_4w;
    if (d > 2) return { dir: "improving", icon: ArrowUpRight, color: "text-emerald-400" };
    if (d < -2) return { dir: "declining", icon: ArrowDownRight, color: "text-rose-400" };
    return { dir: "stable", icon: Minus, color: "text-white/55" };
  }, [data]);

  if (loading) return <main className="mx-auto max-w-6xl px-6 py-16 text-white/55">Loading dashboard…</main>;
  if (!data) return <main className="mx-auto max-w-6xl px-6 py-16 text-rose-300">Failed to load data. Try refreshing.</main>;

  const TrendIcon = trend.icon;
  const totalSent = data.sentiment_distribution.positive + data.sentiment_distribution.negative + data.sentiment_distribution.neutral;
  const sentimentPie = [
    { name: "Positive", value: data.sentiment_distribution.positive, color: SENTIMENT_COLORS.positive },
    { name: "Neutral", value: data.sentiment_distribution.neutral, color: SENTIMENT_COLORS.neutral },
    { name: "Negative", value: data.sentiment_distribution.negative, color: SENTIMENT_COLORS.negative },
  ];

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      {/* ── HERO ──────────────────────────────────────────────────── */}
      <header className="mb-12">
        <p className="font-mono text-xs uppercase tracking-[0.32em] text-accent/85">~/gambia/political-risk-index</p>
        <h1 className="mt-3 text-balance text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-tight">
          What is The Gambia&apos;s news climate like this week?
        </h1>
        <p className="mt-4 max-w-3xl text-pretty text-base leading-relaxed text-white/65">
          I scraped <strong className="text-white">{data.summary.n_articles_total} articles</strong> from{" "}
          <strong className="text-white">{data.summary.n_sources} Gambian news publications</strong>, ran them
          through sentiment analysis and topic modelling, and condensed it all into a single weekly score
          from 0 to 100. <strong className="text-white">Higher = more positive, calmer news environment.</strong>{" "}
          Lower = more political stress, crime, and negative coverage. Below is what the data says — with the
          actual headlines so you can see what&apos;s driving each number.
        </p>
      </header>

      {/* ── TOP-LEVEL STATS ───────────────────────────────────────── */}
      <section className="mb-12 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-accent/30 bg-accent/[0.04] p-5">
          <p className="font-mono text-[10px] uppercase tracking-wider text-accent/85">PRI this week</p>
          <p className="mt-2 text-4xl font-semibold tabular-nums">{data.summary.current_pri.toFixed(1)}</p>
          <p className={`mt-2 inline-flex items-center gap-1 text-xs ${trend.color}`}>
            <TrendIcon className="h-3.5 w-3.5" /> {trend.dir} ({data.summary.delta_4w >= 0 ? "+" : ""}
            {data.summary.delta_4w.toFixed(1)} vs 4 wks ago)
          </p>
        </div>
        <Stat label="Articles analysed" value={data.summary.n_articles_total.toLocaleString()} />
        <Stat label="News sources" value={data.summary.n_sources.toString()} />
        <Stat label="Weeks covered" value={data.summary.n_weeks.toString()} />
      </section>

      {/* ── PRI CHART ─────────────────────────────────────────────── */}
      <section className="mb-12 rounded-2xl border border-white/10 bg-surface p-5 md:p-7">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-medium">Weekly news climate, {data.summary.first_week} → {data.summary.last_week}</h2>
          <p className="text-xs text-white/45">red dashes = known events</p>
        </div>
        <div className="h-96 w-full">
          <ResponsiveContainer>
            <LineChart data={data.pri_series.map((p) => ({ ...p, ts: new Date(p.week).getTime() }))}>
              <CartesianGrid stroke="#1a1d24" strokeDasharray="3 3" />
              <XAxis
                dataKey="ts" type="number" domain={["dataMin", "dataMax"]}
                tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
                stroke="#888"
              />
              <YAxis domain={[0, 100]} stroke="#888" />
              <Tooltip
                contentStyle={{ background: "#0b0d12", border: "1px solid #1a1d24", borderRadius: 8 }}
                labelFormatter={(v) => new Date(v as number).toLocaleDateString()}
                formatter={(value: number) => [value.toFixed(1), "PRI"]}
              />
              <Line type="monotone" dataKey="pri" stroke="#00f0ff" strokeWidth={2} dot={{ r: 2.5 }} />
              {ELECTION_EVENTS.filter((e) => {
                if (data.pri_series.length === 0) return false;
                const t = new Date(e.date).getTime();
                return t >= new Date(data.pri_series[0].week).getTime() &&
                       t <= new Date(data.pri_series.at(-1)!.week).getTime();
              }).map((e) => (
                <ReferenceLine key={e.date} x={new Date(e.date).getTime()} stroke="#ff5577" strokeDasharray="2 4"
                  label={{ value: e.label, fill: "#ff5577", fontSize: 10, position: "top" }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* ── SENTIMENT + SOURCES ───────────────────────────────────── */}
      <section className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-5">
        <div className="rounded-2xl border border-white/10 bg-surface p-5 md:col-span-2">
          <h3 className="mb-1 text-base font-medium">Tone across all coverage</h3>
          <p className="mb-4 text-xs text-white/55">
            Each article classified by distilBERT-SST2 fine-tuned on Stanford Sentiment Treebank.
          </p>
          <div className="h-56">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={sentimentPie} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={3}>
                  {sentimentPie.map((s) => <Cell key={s.name} fill={s.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#0b0d12", border: "1px solid #1a1d24", borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
            {sentimentPie.map((s) => (
              <div key={s.name}>
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
                <span className="ml-1.5 text-white/65">{s.name}</span>
                <p className="mt-0.5 font-mono tabular-nums text-white/85">{((s.value / totalSent) * 100).toFixed(0)}%</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-surface p-5 md:col-span-3">
          <h3 className="mb-1 text-base font-medium">Where the articles came from</h3>
          <p className="mb-4 text-xs text-white/55">
            Articles per publication, coloured by their average tone (green = positive lean, red = negative lean).
          </p>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={data.sources} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid stroke="#1a1d24" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" stroke="#888" />
                <YAxis type="category" dataKey="source" stroke="#aaa" width={100} fontSize={12} />
                <Tooltip
                  contentStyle={{ background: "#0b0d12", border: "1px solid #1a1d24", borderRadius: 8 }}
                  formatter={(value: number, name: string, props) => {
                    const ms = props.payload.mean_sentiment as number;
                    return [`${value} articles · tone ${ms.toFixed(2)}`, props.payload.source];
                  }}
                />
                <Bar dataKey="n_articles">
                  {data.sources.map((s, i) => (
                    <Cell key={i} fill={s.mean_sentiment > 0.6 ? "#34d399" : s.mean_sentiment < 0.4 ? "#fb7185" : "#00f0ff"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      {/* ── TOPICS ────────────────────────────────────────────────── */}
      <section className="mb-12">
        <h2 className="mb-2 flex items-center gap-2 text-lg font-medium">
          <Tag className="h-4 w-4 text-accent" /> What Gambian news is actually about
        </h2>
        <p className="mb-5 text-sm text-white/60">
          K-Means clustering on sentence-transformer embeddings (all-MiniLM-L6-v2) groups the 391 articles
          into 8 themes. Each card shows a representative positive and negative headline so you can sanity-check the model.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.topics.map((t) => (
            <article key={t.id} className="rounded-2xl border border-white/10 bg-surface p-5">
              <header className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold">{t.label}</h3>
                  <p className="mt-0.5 text-[11px] text-white/45">{t.keywords.slice(0, 6).join(" · ")}</p>
                </div>
                <span className="shrink-0 rounded-full bg-white/5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-white/65">
                  {t.n_articles} articles
                </span>
              </header>
              <div className="mb-3 flex gap-4 text-[11px]">
                <span className="text-emerald-300/85">+ {(t.positive_share * 100).toFixed(0)}% positive</span>
                <span className="text-rose-300/85">− {(t.negative_share * 100).toFixed(0)}% negative</span>
              </div>
              {t.sample_positive[0] && (
                <a href={t.sample_positive[0].url} target="_blank" rel="noreferrer noopener"
                  className="mb-2 block rounded-lg border border-emerald-400/15 bg-emerald-400/[0.04] p-3 text-sm text-white/80 hover:border-emerald-400/30">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-emerald-300/75">positive sample · {t.sample_positive[0].source}</span>
                  <p className="mt-1 leading-snug">{t.sample_positive[0].headline}</p>
                </a>
              )}
              {t.sample_negative[0] && (
                <a href={t.sample_negative[0].url} target="_blank" rel="noreferrer noopener"
                  className="block rounded-lg border border-rose-400/15 bg-rose-400/[0.04] p-3 text-sm text-white/80 hover:border-rose-400/30">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-rose-300/75">negative sample · {t.sample_negative[0].source}</span>
                  <p className="mt-1 leading-snug">{t.sample_negative[0].headline}</p>
                </a>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* ── MOST POSITIVE / NEGATIVE RECENT HEADLINES ─────────────── */}
      <section className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-2">
        <HeadlineList title="Most positive recent headlines" icon={ThumbsUp} accent="emerald" items={data.most_positive} />
        <HeadlineList title="Most negative recent headlines" icon={ThumbsDown} accent="rose" items={data.most_negative} />
      </section>

      {/* ── METHODOLOGY ───────────────────────────────────────────── */}
      <section className="rounded-2xl border border-white/10 bg-surface p-5 md:p-7">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-medium">
          <Newspaper className="h-4 w-4 text-accent" /> How this was built
        </h2>
        <ol className="ml-5 list-decimal space-y-2.5 text-sm leading-relaxed text-white/70">
          <li><strong className="text-white/90">Scrape</strong> articles politely from six Gambian publications with 1-3s random delays and per-page failure tolerance.</li>
          <li><strong className="text-white/90">Preprocess</strong> with NLTK: lowercase, strip HTML/URLs, tokenise, lemmatise, drop stopwords, dedupe.</li>
          <li><strong className="text-white/90">Featurise</strong>: TF-IDF (8 355 features, bigrams) plus sentence-transformer embeddings (all-MiniLM-L6-v2, 384-d).</li>
          <li><strong className="text-white/90">Score sentiment</strong> with VADER (lexicon baseline) and distilBERT-SST2 (transformer). DistilBERT&apos;s confidence is used downstream.</li>
          <li><strong className="text-white/90">Cluster topics</strong> with K-Means on the embeddings (silhouette-validated), with top TF-IDF terms surfaced per cluster.</li>
          <li><strong className="text-white/90">Composite PRI</strong>: 40 % mean sentiment + 30 % (1 − negative share) + 20 % (1 − political prevalence) + 10 % (1 − crime prevalence), min-max normalised.</li>
          <li><strong className="text-white/90">Validate</strong>: annotate the chart with known Gambian events to sanity-check that turbulence shows up where it should.</li>
        </ol>
        <p className="mt-5 text-xs text-white/40">
          Data generated {data.summary.last_week}. Sources: The Point · Foroyaa · Standard · Kaironews · The Voice · Alkamba Times.
        </p>
      </section>

      <footer className="mt-12 text-center text-xs text-white/35">
        Built by Abdoulie Balisa.{" "}
        <a href="https://balisa50.github.io" target="_blank" rel="noreferrer noopener" className="underline-offset-2 hover:text-accent hover:underline">portfolio</a>{" "}·{" "}
        <a href="https://github.com/Balisa50/gambia-political-risk" target="_blank" rel="noreferrer noopener" className="underline-offset-2 hover:text-accent hover:underline">
          source <ExternalLink className="ml-0.5 inline h-3 w-3" />
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

function HeadlineList({
  title, icon: Icon, accent, items,
}: { title: string; icon: typeof ThumbsUp; accent: "emerald" | "rose"; items: Headline[] }) {
  const borderClass = accent === "emerald" ? "border-emerald-400/15 hover:border-emerald-400/35" : "border-rose-400/15 hover:border-rose-400/35";
  const iconClass = accent === "emerald" ? "text-emerald-400" : "text-rose-400";
  return (
    <div className="rounded-2xl border border-white/10 bg-surface p-5">
      <h3 className="mb-4 flex items-center gap-2 text-base font-medium">
        <Icon className={`h-4 w-4 ${iconClass}`} /> {title}
      </h3>
      <ul className="space-y-2">
        {items.map((h, i) => (
          <li key={i}>
            <a href={h.url} target="_blank" rel="noreferrer noopener"
              className={`block rounded-lg border bg-white/[0.02] p-3 text-sm text-white/80 transition ${borderClass}`}>
              <p className="leading-snug">{h.headline}</p>
              <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-white/45">
                {h.source} · {h.date} · score {h.sentiment?.toFixed(2)}
              </p>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
