"use client";

import { FormEvent, ReactElement, useState } from "react";
import axios from "axios";
import { AlertCircle, BarChart3, Loader2, RefreshCw, SearchX } from "lucide-react";

import { AnalyticsFilters, AnalyticsResponse, getAnalytics } from "@/lib/api";
import { formatDate, formatPercentRatio } from "@/lib/backtests-format";
import { EquityCurveChart } from "@/components/charts/equity-curve-chart";

const panelClass = "rounded-atlas-md border border-atlas-border bg-atlas-surface";
const inputClass =
  "mt-atlas-1 w-full rounded-atlas border border-atlas-border bg-atlas-bg-elevated px-atlas-3 py-[10px] text-atlas-md leading-atlas-normal text-atlas-fg outline-none transition-colors duration-atlas-base ease-atlas-out focus:border-atlas-accent focus:ring-2 focus:ring-atlas-accent/20";

function formatRatio(value: number | null, digits = 2): string {
  return value === null ? "Not defined" : value.toFixed(digits);
}

function formatPercent(value: string): string {
  const formatted = formatPercentRatio(value);
  return formatted.startsWith("-") ? formatted : `+${formatted}`;
}

function Metric({ label, value, detail, tone }: { label: string; value: string; detail?: string; tone?: string }): ReactElement {
  return (
    <div className="border-b border-atlas-border pb-atlas-4 last:border-b-0 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-atlas-5 lg:border-r-0 lg:border-b lg:pb-atlas-5 lg:pr-0 lg:last:border-b-0">
      <dt className="text-atlas-xs leading-atlas-snug text-atlas-fg-secondary">{label}</dt>
      <dd className={`mt-atlas-2 font-atlas-mono text-atlas-xl leading-atlas-tight ${tone ?? "text-atlas-fg"}`}>{value}</dd>
      {detail && <dd className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">{detail}</dd>}
    </div>
  );
}

function EquityCurve({ analytics }: { analytics: AnalyticsResponse }): ReactElement {
  if (analytics.equity_curve.length < 2) {
    return (
      <div className="flex min-h-56 flex-col items-center justify-center px-atlas-5 py-atlas-8 text-center">
        <SearchX className="size-7 text-atlas-fg-secondary" aria-hidden="true" />
        <p className="mt-atlas-3 text-atlas-md font-atlas-semibold text-atlas-fg">No closed-trade curve yet</p>
        <p className="mt-atlas-1 text-atlas-sm text-atlas-fg-secondary">A curve appears after at least one closed trade is recorded.</p>
      </div>
    );
  }

  return (
    <div className="p-atlas-4 sm:p-atlas-6">
      <div className="flex items-center justify-between text-atlas-xs text-atlas-fg-secondary"><span>API-provided equity</span><span>UTC</span></div>
      <div className="mt-atlas-3 overflow-hidden rounded-atlas border border-atlas-border"><EquityCurveChart points={analytics.equity_curve} /></div>
      <div className="mt-atlas-3 text-right text-atlas-xs text-atlas-fg-secondary">{analytics.equity_curve.length} API-provided points</div>
      <div className="sr-only" aria-label="Equity curve data table">
        <table><caption>API-provided closed-trade equity points</caption><thead><tr><th scope="col">UTC time</th><th scope="col">Equity</th></tr></thead><tbody>{analytics.equity_curve.map((point) => <tr key={`table-${point.timestamp}-${point.trade_id ?? "baseline"}`}><td>{formatDate(point.timestamp)}</td><td>{point.equity}</td></tr>)}</tbody></table>
      </div>
    </div>
  );
}

export default function AnalyticsView({ initialAnalytics, initialLoadError }: { initialAnalytics: AnalyticsResponse | null; initialLoadError?: string }): ReactElement {
  const [analytics, setAnalytics] = useState(initialAnalytics);
  const [error, setError] = useState(initialLoadError ?? "");
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  async function load(event?: FormEvent<HTMLFormElement>): Promise<void> {
    event?.preventDefault();
    setError("");
    const start = startDate ? new Date(`${startDate}Z`) : null;
    const end = endDate ? new Date(`${endDate}Z`) : null;
    if ((start && Number.isNaN(start.getTime())) || (end && Number.isNaN(end.getTime()))) {
      setError("Enter valid UTC dates.");
      return;
    }
    if (start && end && end < start) {
      setError("End date must be on or after the start date.");
      return;
    }
    const filters: AnalyticsFilters = {};
    if (start) filters.start_date = start.toISOString();
    if (end) filters.end_date = end.toISOString();
    setLoading(true);
    try {
      setAnalytics(await getAnalytics(filters));
    } catch (cause) {
      const detail = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "Unable to load analytics for this range.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-atlas-8 flex flex-col gap-atlas-4 border-b border-atlas-border pb-atlas-6 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="font-atlas-mono text-atlas-xs text-atlas-accent">PERFORMANCE REVIEW</p><h1 className="mt-atlas-2 text-atlas-3xl font-atlas-semibold leading-atlas-tight tracking-atlas-tight">Analytics</h1><p className="mt-atlas-2 max-w-2xl text-atlas-md text-atlas-fg-secondary">Understand how closed trades have performed over time. Metrics and the equity curve are computed by the API.</p></div>
          <button type="button" onClick={() => void load()} disabled={loading} className="inline-flex min-h-atlas-10 items-center justify-center gap-atlas-2 rounded-atlas border border-atlas-border px-atlas-4 py-atlas-2 text-atlas-md font-atlas-semibold hover:bg-atlas-bg-elevated focus:outline-none focus:ring-2 focus:ring-atlas-accent/30 disabled:cursor-not-allowed disabled:opacity-60">{loading ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />} Refresh</button>
        </header>
        <form onSubmit={load} className={`${panelClass} mb-atlas-6 p-atlas-5 sm:p-atlas-6`} aria-labelledby="range-heading"><div className="flex flex-col gap-atlas-4 lg:flex-row lg:items-end lg:justify-between"><div><h2 id="range-heading" className="text-atlas-lg font-atlas-semibold">Date range</h2><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">Optional bounds are interpreted and sent as UTC.</p></div><div className="grid flex-1 gap-atlas-4 sm:grid-cols-2 lg:max-w-2xl"><label className="text-atlas-sm font-atlas-semibold">Start (UTC)<input type="datetime-local" value={startDate} onChange={(event) => setStartDate(event.target.value)} className={inputClass} /></label><label className="text-atlas-sm font-atlas-semibold">End (UTC)<input type="datetime-local" value={endDate} onChange={(event) => setEndDate(event.target.value)} className={inputClass} /></label></div><button type="submit" disabled={loading} className="inline-flex min-h-atlas-10 items-center justify-center gap-atlas-2 rounded-atlas bg-atlas-accent px-atlas-5 py-atlas-2 text-atlas-md font-atlas-semibold text-white hover:bg-atlas-accent-dim focus:outline-none focus:ring-2 focus:ring-atlas-accent/40 disabled:cursor-not-allowed disabled:opacity-60">{loading && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}Apply range</button></div></form>
        {error && <div className="mb-atlas-5 flex items-center gap-atlas-3 rounded-atlas bg-atlas-negative-dim p-atlas-4 text-atlas-md text-atlas-negative" role="alert"><AlertCircle className="size-4 shrink-0" aria-hidden="true" />{error}</div>}
        {!analytics && !loading && <section className={`${panelClass} flex flex-col items-center px-atlas-5 py-[56px] text-center`}><SearchX className="size-7 text-atlas-fg-secondary" aria-hidden="true" /><h2 className="mt-atlas-3 text-atlas-lg font-atlas-semibold">No analytics available</h2><p className="mt-atlas-1 max-w-md text-atlas-md text-atlas-fg-secondary">Connect to the API or select another date range to view closed-trade performance.</p></section>}
        {analytics && <><section className={`${panelClass} p-atlas-5 sm:p-atlas-6`} aria-labelledby="metrics-heading"><div className="flex items-center gap-atlas-3"><BarChart3 className="size-5 text-atlas-accent" aria-hidden="true" /><div><h2 id="metrics-heading" className="text-atlas-lg font-atlas-semibold">Performance snapshot</h2><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">Closed trades only · {analytics.total_trades} total</p></div></div><dl className="mt-atlas-6 grid gap-atlas-5 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Total return" value={formatPercent(analytics.total_return)} tone={analytics.total_return.startsWith("-") ? "text-atlas-negative" : "text-atlas-positive"} /><Metric label="Total P&L" value={analytics.total_pnl} tone={analytics.total_pnl.startsWith("-") ? "text-atlas-negative" : "text-atlas-positive"} /><Metric label="Starting equity" value={analytics.starting_equity} /><Metric label="Ending equity" value={analytics.ending_equity} /><Metric label="Win rate" value={`${(analytics.win_rate * 100).toFixed(2)}%`} detail={`${analytics.winning_trades} winning · ${analytics.losing_trades} losing`} /><Metric label="Closed-trade daily Sharpe" value={formatRatio(analytics.closed_trade_daily_sharpe)} detail={analytics.closed_trade_daily_sharpe === null ? "Insufficient observations or zero variance" : "365-day annualization"} /><Metric label="Max drawdown (absolute)" value={analytics.max_drawdown} tone="text-atlas-negative" /><Metric label="Profit factor" value={formatRatio(analytics.profit_factor)} detail={analytics.profit_factor === null ? "Not defined when there are no losses" : undefined} /></dl></section><section className={`${panelClass} mt-atlas-6 overflow-hidden`} aria-labelledby="curve-heading"><div className="border-b border-atlas-border px-atlas-5 py-atlas-4 sm:px-atlas-6"><h2 id="curve-heading" className="text-atlas-lg font-atlas-semibold">Closed-trade equity curve</h2><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">API-provided equity after each closed trade, including the starting baseline.</p></div><EquityCurve analytics={analytics} /></section></>}
      </div>
    </main>
  );
}
