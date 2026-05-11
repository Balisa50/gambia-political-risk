"use client";

import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
  BarChart, Bar, Cell, PieChart, Pie,
} from "recharts";
import { ArrowUpRight, ArrowDownRight, Minus, ThumbsUp, ThumbsDown } from "lucide-react";

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

  if (loading) return <main className="mx-auto max-w-6xl px-6 py-16 text-white/55">Loading…</main>;
  if (!data) return <main className="mx-auto max-w-6xl px-6 py-16 text-rose-300">Failed to load data.</main>;

  const TrendIcon = trend.icon;
  const totalSent = data.sentiment_distribution.positive + data.sentiment_distribution.negative + data.sentiment_distribution.neutral;
  const sentimentPie = [
    { name: "Positive", value: data.sentiment_distribution.positive, color: SENTIMENT_COLORS.positive },
    { name: "Neutral", value: data.sentiment_distribution.neutral, color: SENTIMENT_COLORS.neutral },
    { name: "Negative", value: data.sentiment_distribution.negative, color: SENTIMENT_COLORS.negative },
  ];

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      {/* ── HERO ─────────────────────────────────────────────────── */}
      <header className="mb-12">
        <p className="font-mono text-xs uppercase tracking-[0.32em] text-accent/85">The Gambia · news climate</p>
        <h1 className="mt-3 text-balance text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-tight">
          How is the news in The Gambia this week?
        </h1>
        <p className="mt-4 max-w-2xl text-pretty text-base leading-relaxed text-white/65">
          A single score from 0 to 100 that summarises the tone of Gambian news coverage week by week.{" "}
          Higher means calmer, more positive reporting. Lower means more negative coverage, political stress, and crime.
        </p>
      </header>

      {/* ── HEADLINE STATS ───────────────────────────────────────── */}
      <section className="mb-12 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-accent/30 bg-accent/[0.04] p-5">
          <p className="font-mono text-[10px] uppercase tracking-wider text-accent/85">This week</p>
          <p className="mt-2 text-4xl font-semibold tabular-nums">{data.summary.current_pri.toFixed(0)}</p>
          <p className={`mt-2 inline-flex items-center gap-1 text-xs ${trend.color}`}>
            <TrendIcon className="h-3.5 w-3.5" /> {trend.dir} ({data.summary.delta_4w >= 0 ? "+" : ""}
            {data.summary.delta_4w.toFixed(1)} vs a month ago)
          </p>
        </div>
        <Stat label="Articles read" value={data.summary.n_articles_total.toLocaleString()} />
        <Stat label="Newspapers" value={data.summary.n_sources.toString()} />
        <Stat label="Weeks tracked" value={data.summary.n_weeks.toString()} />
      </section>

      {/* ── PRI CHART ────────────────────────────────────────────── */}
      <section className="mb-12 rounded-2xl border border-white/10 bg-surface p-5 md:p-7">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-medium">The news climate over time</h2>
          <p className="text-xs text-white/45">dashed lines = major events</p>
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
                formatter={(value: number) => [value.toFixed(1), "Score"]}
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

      {/* ── TONE + SOURCES ───────────────────────────────────────── */}
      <section className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-5">
        <div className="rounded-2xl border border-white/10 bg-surface p-5 md:col-span-2">
          <h3 className="mb-4 text-base font-medium">Overall tone of coverage</h3>
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
          <h3 className="mb-4 text-base font-medium">Coverage by newspaper</h3>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={data.sources} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid stroke="#1a1d24" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" stroke="#888" />
                <YAxis type="category" dataKey="source" stroke="#aaa" width={100} fontSize={12} />
                <Tooltip
                  contentStyle={{ background: "#0b0d12", border: "1px solid #1a1d24", borderRadius: 8 }}
                  formatter={(value: number, _name: string, props) => [`${value} articles`, props.payload.source]}
                />
                <Bar dataKey="n_articles">
                  {data.sources.map((s, i) => (
                    <Cell key={i} fill={s.mean_sentiment > 0.6 ? "#34d399" : s.mean_sentiment < 0.4 ? "#fb7185" : "#00f0ff"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-[11px] text-white/40">Bar colour reflects the newspaper&apos;s average tone — green leans positive, red leans negative.</p>
        </div>
      </section>

      {/* ── WHAT THE NEWS IS ABOUT ───────────────────────────────── */}
      <section className="mb-12">
        <h2 className="mb-5 text-lg font-medium">What the news is about</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.topics.map((t) => (
            <article key={t.id} className="rounded-2xl border border-white/10 bg-surface p-5">
              <header className="mb-3 flex items-start justify-between gap-3">
                <h3 className="text-base font-semibold">{t.label}</h3>
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
                  <p className="leading-snug">{t.sample_positive[0].headline}</p>
                  <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-emerald-300/65">{t.sample_positive[0].source}</p>
                </a>
              )}
              {t.sample_negative[0] && (
                <a href={t.sample_negative[0].url} target="_blank" rel="noreferrer noopener"
                  className="block rounded-lg border border-rose-400/15 bg-rose-400/[0.04] p-3 text-sm text-white/80 hover:border-rose-400/30">
                  <p className="leading-snug">{t.sample_negative[0].headline}</p>
                  <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-rose-300/65">{t.sample_negative[0].source}</p>
                </a>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* ── HEADLINE LISTS ───────────────────────────────────────── */}
      <section className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-2">
        <HeadlineList title="Most positive recent headlines" icon={ThumbsUp} accent="emerald" items={data.most_positive} />
        <HeadlineList title="Most negative recent headlines" icon={ThumbsDown} accent="rose" items={data.most_negative} />
      </section>

      <footer className="mt-12 text-center text-xs text-white/35">
        Built by Abdoulie Balisa · data refreshed {data.summary.last_week}
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
                {h.source} · {h.date}
              </p>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
