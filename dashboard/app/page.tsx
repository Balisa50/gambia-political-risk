"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

interface PriPoint {
  date: string;
  score: number;
  n_articles: number;
  event: string | null;
}
interface CurrentPri {
  date: string;
  score: number;
  trend: "improving" | "declining" | "stable";
  delta_4w: number;
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [series, setSeries] = useState<PriPoint[]>([]);
  const [current, setCurrent] = useState<CurrentPri | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/risk-index`).then((r) => (r.ok ? r.json() : [])),
      fetch(`${API}/risk-index/current`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([s, c]) => {
        setSeries(s);
        setCurrent(c);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-10">
        <p className="font-mono text-xs uppercase tracking-[0.32em] text-accent/85">~/gambia/political-risk-index</p>
        <h1 className="mt-3 text-balance text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-tight">
          The Gambia Political Risk Index
        </h1>
        <p className="mt-3 max-w-2xl text-pretty text-base leading-relaxed text-white/60">
          A weekly 0-100 score derived from sentiment, topic prevalence, and crime coverage in
          Gambian news media. Higher means a more stable, positive news environment.
        </p>
      </header>

      {/* Current */}
      <section className="mb-10 grid grid-cols-1 gap-4 md:grid-cols-3">
        <CurrentScore current={current} />
        <Stat label="Articles in latest week" value={series.at(-1)?.n_articles?.toLocaleString() ?? "-"} />
        <Stat label="Weeks observed" value={series.length.toLocaleString()} />
      </section>

      {/* Chart */}
      <section className="rounded-2xl border border-white/10 bg-surface p-5 md:p-7">
        <h2 className="mb-4 text-lg font-medium">Weekly PRI</h2>
        {loading ? (
          <p className="text-white/45">Loading…</p>
        ) : series.length === 0 ? (
          <p className="text-white/45">
            No data yet. Run the notebooks 01-07 to generate{" "}
            <code className="rounded bg-white/10 px-1.5 py-0.5">outputs/political_risk_index.csv</code>.
          </p>
        ) : (
          <div className="h-96 w-full">
            <ResponsiveContainer>
              <LineChart data={series.map((p) => ({ ...p, ts: new Date(p.date).getTime() }))}>
                <CartesianGrid stroke="#1a1d24" strokeDasharray="3 3" />
                <XAxis dataKey="ts" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", year: "2-digit" })} stroke="#888" />
                <YAxis domain={[0, 100]} stroke="#888" />
                <Tooltip contentStyle={{ background: "#0b0d12", border: "1px solid #1a1d24" }} labelFormatter={(v) => new Date(v as number).toLocaleDateString()} />
                <Line type="monotone" dataKey="score" stroke="#00f0ff" strokeWidth={2} dot={false} />
                {series
                  .filter((p) => p.event)
                  .map((p) => (
                    <ReferenceLine key={p.date} x={new Date(p.date).getTime()} stroke="#ff5577" strokeDasharray="2 4" label={{ value: p.event ?? "", fill: "#ff5577", fontSize: 10, position: "top" }} />
                  ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      {/* Analyze text */}
      <Analyze />

      <footer className="mt-12 text-center text-xs text-white/35">
        Data: The Point, Foroyaa, Gainako, Standard. Models: distilBERT-SST2 (sentiment), LDA + K-Means (topics).
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

function CurrentScore({ current }: { current: CurrentPri | null }) {
  const TrendIcon = current?.trend === "improving" ? ArrowUpRight : current?.trend === "declining" ? ArrowDownRight : Minus;
  const trendColor = current?.trend === "improving" ? "text-emerald-400" : current?.trend === "declining" ? "text-rose-400" : "text-white/55";
  return (
    <div className="rounded-2xl border border-accent/30 bg-accent/[0.03] p-5">
      <p className="font-mono text-[10px] uppercase tracking-wider text-accent/85">Current PRI</p>
      <p className="mt-2 text-4xl font-semibold tabular-nums">{current ? current.score.toFixed(1) : "-"}</p>
      {current && (
        <p className={`mt-2 inline-flex items-center gap-1 text-xs ${trendColor}`}>
          <TrendIcon className="h-3.5 w-3.5" /> {current.trend} ({current.delta_4w >= 0 ? "+" : ""}
          {current.delta_4w.toFixed(1)} vs 4 wks ago)
        </p>
      )}
    </div>
  );
}

function Analyze() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<{ sentiment: string; confidence: number; risk_contribution: number } | null>(null);

  const submit = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setOut(null);
    try {
      const r = await fetch(`${API}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (r.ok) setOut(await r.json());
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mt-10 rounded-2xl border border-white/10 bg-surface p-5 md:p-7">
      <h2 className="mb-4 text-lg font-medium">Analyse a headline or article</h2>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste a Gambian news headline or article text..."
        className="min-h-[120px] w-full rounded-lg border border-white/10 bg-black/50 px-4 py-3 text-sm placeholder:text-white/30 focus:border-accent/60 focus:outline-none"
      />
      <div className="mt-3 flex items-center gap-3">
        <button onClick={submit} disabled={busy || !text.trim()} className="rounded-full bg-accent px-5 py-2 text-sm font-medium text-background transition disabled:opacity-50">
          {busy ? "Analysing…" : "Analyse"}
        </button>
        {out && (
          <div className="flex items-center gap-3 text-sm">
            <span className={out.sentiment === "positive" ? "text-emerald-400" : "text-rose-400"}>{out.sentiment}</span>
            <span className="text-white/55">{(out.confidence * 100).toFixed(1)}% conf</span>
            <span className="text-white/55">risk contribution {out.risk_contribution.toFixed(1)}</span>
          </div>
        )}
      </div>
    </section>
  );
}
