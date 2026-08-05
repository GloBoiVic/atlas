"use client";

import { FormEvent, ReactElement, useState } from "react";
import axios from "axios";
import {
  AlertCircle,
  ArrowLeft,
  ChevronRight,
  Loader2,
  Play,
  SearchX,
} from "lucide-react";

import {
  BacktestCreateRequest,
  BacktestRun,
  BacktestTrade,
  createBacktest,
  getBacktest,
  getBacktestTrades,
  listBacktests,
} from "@/lib/api";
import { formatDate, formatDecimal, formatPercentRatio } from "@/lib/backtests-format";
import Metric from "@/app/backtests/metric";
import StatusBadge from "@/app/backtests/status-badge";
import StatusMessage from "@/app/backtests/status-message";

const inputClass =
  // 10px vertical padding preserves the existing compact control height; no Atlas 2.5 token exists.
  "mt-atlas-1 w-full rounded-atlas border border-atlas-border bg-atlas-bg-elevated px-atlas-3 py-[10px] text-atlas-md leading-atlas-normal text-atlas-fg outline-none transition-colors duration-atlas-base ease-atlas-out placeholder:text-atlas-fg-secondary focus:border-atlas-accent focus:ring-2 focus:ring-atlas-accent/20";
const panelClass = "rounded-atlas-md border border-atlas-border bg-atlas-surface";
type FormState = Omit<BacktestCreateRequest, "strategy_parameters" | "risk_config" | "execution_config">;
const initialForm: FormState = {
  instrument_id: "",
  account_id: "",
  strategy_version_id: "",
  timeframe: "1h",
  start_date: "",
  end_date: "",
  initial_balance: "10000",
};

function RunForm({ onCreated }: { onCreated: (run: BacktestRun) => void }) {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const update = (key: keyof FormState, value: string): void => setForm((current) => ({ ...current, [key]: value }));

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    const startDate = new Date(`${form.start_date}Z`);
    const endDate = new Date(`${form.end_date}Z`);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
      setError("Enter valid UTC start and end dates.");
      return;
    }
    if (endDate < startDate) {
      setError("End date must be on or after the start date.");
      return;
    }
    setSubmitting(true);
    const request: BacktestCreateRequest = {
      ...form,
      start_date: startDate.toISOString(),
      end_date: endDate.toISOString(),
      strategy_parameters: {},
      risk_config: {},
      execution_config: { fill_model: "next_candle_open", protective_trigger_rule: "stop_loss_first" },
    };
    try {
      onCreated(await createBacktest(request));
    } catch (cause) {
      const message = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
      setError(typeof message === "string" ? message : "The backtest could not be started. Check the inputs and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const fields: Array<[keyof FormState, string, string]> = [
    ["instrument_id", "Instrument ID", "UUID from the data catalog"],
    ["account_id", "Account ID", "UUID for the starting balance scope"],
    ["strategy_version_id", "Strategy version ID", "Registered version UUID"],
  ];
  return (
    <section className={`${panelClass} p-atlas-5 sm:p-atlas-6`} aria-labelledby="run-form-heading">
      <h2 id="run-form-heading" className="text-atlas-xl font-atlas-semibold leading-atlas-tight text-atlas-fg">Run a backtest</h2>
      <p className="mt-atlas-1 text-atlas-md leading-atlas-normal text-atlas-fg-secondary">Replay persisted candles with the selected strategy version.</p>
      <form className="mt-atlas-6 space-y-atlas-5" onSubmit={submit}>
        <div className="grid gap-atlas-4 md:grid-cols-3">
          {fields.map(([key, label, hint]) => <label key={key} className="block text-atlas-sm font-atlas-semibold leading-atlas-snug text-atlas-fg">{label}<input required type="text" value={form[key]} onChange={(event) => update(key, event.target.value)} placeholder={hint} className={inputClass} aria-label={label} /></label>)}
        </div>
        <div className="grid gap-atlas-4 sm:grid-cols-3">
          <label className="text-atlas-sm font-atlas-semibold leading-atlas-snug text-atlas-fg">Timeframe<select value={form.timeframe} onChange={(event) => update("timeframe", event.target.value)} className={inputClass}><option>1m</option><option>5m</option><option>15m</option><option>1h</option><option>4h</option><option>1d</option></select></label>
          <label className="text-atlas-sm font-atlas-semibold leading-atlas-snug text-atlas-fg">Start (UTC)<input required type="datetime-local" value={form.start_date} onChange={(event) => update("start_date", event.target.value)} className={inputClass} aria-describedby="utc-date-hint" /></label>
          <label className="text-atlas-sm font-atlas-semibold leading-atlas-snug text-atlas-fg">End (UTC)<input required type="datetime-local" value={form.end_date} onChange={(event) => update("end_date", event.target.value)} className={inputClass} aria-describedby="utc-date-hint" /></label>
          <p id="utc-date-hint" className="text-atlas-xs font-atlas-regular leading-atlas-normal text-atlas-fg-secondary sm:col-span-3">Enter both times as UTC. The selected clock time is sent unchanged with a UTC offset.</p>
        </div>
        <div className="flex flex-col gap-atlas-4 border-t border-atlas-border pt-atlas-5 sm:flex-row sm:items-end sm:justify-between"><label className="block max-w-xs text-atlas-sm font-atlas-semibold leading-atlas-snug text-atlas-fg">Initial balance<input required inputMode="decimal" value={form.initial_balance} onChange={(event) => update("initial_balance", event.target.value)} className={inputClass} /></label><button disabled={submitting} className="inline-flex min-h-11 items-center justify-center gap-atlas-2 rounded-atlas bg-atlas-accent px-atlas-5 py-[10px] text-atlas-md font-atlas-semibold leading-atlas-normal text-white transition-colors duration-atlas-base ease-atlas-out hover:bg-atlas-accent-dim focus:outline-none focus:ring-2 focus:ring-atlas-accent/40 disabled:cursor-not-allowed disabled:opacity-60">{submitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />} {submitting ? "Starting…" : "Run backtest"}</button></div>
         {error && <p className="rounded-atlas bg-atlas-negative-dim p-atlas-3 text-atlas-md leading-atlas-normal text-atlas-negative" role="alert">{error}</p>}
      </form>
    </section>
  );
}

function RunList({ runs, selected, onSelect }: { runs: BacktestRun[]; selected: string | null; onSelect: (run: BacktestRun) => void }) {
  return <section className={`${panelClass} overflow-hidden`} aria-labelledby="runs-heading"><div className="flex items-center justify-between border-b border-atlas-border px-atlas-5 py-atlas-4"><div><h2 id="runs-heading" className="text-atlas-lg font-atlas-semibold leading-atlas-tight text-atlas-fg">Recent runs</h2><p className="mt-atlas-1 text-atlas-xs leading-atlas-snug text-atlas-fg-secondary">{runs.length} {runs.length === 1 ? "run" : "runs"}</p></div></div>{runs.length === 0 ? <div className="flex flex-col items-center px-atlas-5 py-[56px] text-center"><SearchX className="size-7 text-atlas-fg-secondary" aria-hidden="true" /><p className="mt-atlas-3 text-atlas-lg font-atlas-semibold leading-atlas-tight text-atlas-fg">No backtests yet</p><p className="mt-atlas-1 max-w-xs text-atlas-md leading-atlas-normal text-atlas-fg-secondary">Configure a historical replay above to see its results here.</p></div> : <div className="divide-y divide-atlas-border">{runs.map((run) => <button key={run.id} onClick={() => onSelect(run)} className={`flex w-full items-center justify-between gap-atlas-4 px-atlas-5 py-atlas-4 text-left transition-colors duration-atlas-base ease-atlas-out hover:bg-atlas-bg-elevated focus:outline-none focus:ring-2 focus:ring-inset focus:ring-atlas-accent ${selected === run.id ? "bg-atlas-bg-elevated" : ""}`}><span className="min-w-0"><span className="flex items-center gap-atlas-2"><span className="truncate text-atlas-md font-atlas-semibold leading-atlas-snug text-atlas-fg">{run.strategy_name}</span><StatusBadge status={run.status} /></span><span className="mt-atlas-1 block text-atlas-xs leading-atlas-snug text-atlas-fg-secondary">{run.symbol} · {run.timeframe} · {formatDate(run.created_at)}</span></span><ChevronRight className="size-4 shrink-0 text-atlas-fg-secondary" aria-hidden="true" /></button>)}</div>}</section>;
}

function RunDetail({ run, trades, loading, onBack }: { run: BacktestRun; trades: BacktestTrade[]; loading: boolean; onBack: () => void }) {
  const result = run.result;
  return <section className="space-y-atlas-5" aria-labelledby="detail-heading"><button onClick={onBack} className="inline-flex items-center gap-atlas-2 text-atlas-md leading-atlas-normal text-atlas-fg-secondary hover:text-atlas-fg focus:outline-none focus:underline"><ArrowLeft className="size-4" aria-hidden="true" /> All runs</button><div className={`${panelClass} p-atlas-5 sm:p-atlas-6`}><div className="flex flex-col gap-atlas-4 sm:flex-row sm:items-start sm:justify-between"><div><div className="flex flex-wrap items-center gap-atlas-3"><h2 id="detail-heading" className="text-atlas-2xl font-atlas-semibold leading-atlas-tight text-atlas-fg">{run.strategy_name}</h2><StatusBadge status={run.status} /></div><p className="mt-atlas-2 text-atlas-md leading-atlas-normal text-atlas-fg-secondary">{run.symbol} · {run.timeframe} · {formatDate(run.start_date)} — {formatDate(run.end_date)}</p></div><span className="font-atlas-mono text-atlas-xs leading-atlas-snug text-atlas-fg-secondary">{run.id.slice(0, 8)}…</span></div><StatusMessage status={run.status} error={run.error_message} />{result && <dl className="mt-atlas-6 grid gap-x-atlas-8 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Total return" value={formatPercentRatio(result.total_return)} tone={result.total_return.startsWith("-") ? "text-atlas-negative" : "text-atlas-positive"} /><Metric label="Total P&L" value={formatDecimal(result.total_pnl)} tone={result.total_pnl.startsWith("-") ? "text-atlas-negative" : "text-atlas-positive"} /><Metric label="Ending equity" value={formatDecimal(result.ending_equity)} /><Metric label="Max drawdown (absolute)" value={formatDecimal(result.max_drawdown)} tone="text-atlas-negative" /><Metric label="Win rate" value={result.win_rate === null ? "—" : `${(result.win_rate * 100).toFixed(2)}%`} /><Metric label="Profit factor" value={result.profit_factor === null ? "—" : result.profit_factor.toFixed(2)} /><Metric label="Sharpe ratio" value={result.sharpe_ratio === null ? "—" : result.sharpe_ratio.toFixed(2)} /><Metric label="Trades" value={`${result.trade_count} (${result.winning_trade_count}W / ${result.losing_trade_count}L)`} /></dl>}</div>{loading ? <div className={`${panelClass} flex items-center gap-atlas-2 p-atlas-5 text-atlas-md leading-atlas-normal text-atlas-fg-secondary`} role="status"><Loader2 className="size-4 animate-spin" aria-hidden="true" />Loading trades…</div> : <div className={`${panelClass} overflow-hidden`}><div className="overflow-x-auto"><table className="min-w-full text-left text-atlas-md leading-atlas-normal"><thead className="border-b border-atlas-border text-atlas-xs leading-atlas-snug text-atlas-fg-secondary"><tr>{["Direction", "Entry", "Exit", "Quantity", "P&L", "Entry time", "Exit time"].map((heading) => <th key={heading} className="px-atlas-5 py-atlas-3 font-atlas-semibold">{heading}</th>)}</tr></thead><tbody className="divide-y divide-atlas-border">{trades.length === 0 ? <tr><td colSpan={7} className="px-atlas-5 py-atlas-10 text-center text-atlas-md text-atlas-fg-secondary">No trades</td></tr> : trades.map((trade) => <tr key={trade.id}><td className="px-atlas-5 py-atlas-3 text-atlas-fg">{trade.direction}</td><td className="px-atlas-5 py-atlas-3 font-atlas-mono text-atlas-fg">{formatDecimal(trade.entry_price)}</td><td className="px-atlas-5 py-atlas-3 font-atlas-mono text-atlas-fg">{formatDecimal(trade.exit_price)}</td><td className="px-atlas-5 py-atlas-3 font-atlas-mono text-atlas-fg">{formatDecimal(trade.quantity)}</td><td className="px-atlas-5 py-atlas-3 font-atlas-mono text-atlas-fg">{formatDecimal(trade.pnl)}</td><td className="px-atlas-5 py-atlas-3 text-atlas-fg-secondary">{formatDate(trade.entry_time)}</td><td className="px-atlas-5 py-atlas-3 text-atlas-fg-secondary">{formatDate(trade.exit_time)}</td></tr>)}</tbody></table></div></div>}</section>;
}

export default function BacktestsView({ initialRuns, initialLoadError }: { initialRuns: BacktestRun[]; initialLoadError?: string }): ReactElement {
  const [runs, setRuns] = useState(initialRuns);
  const [selected, setSelected] = useState<BacktestRun | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [loadError, setLoadError] = useState(initialLoadError ?? "");
  async function selectRun(run: BacktestRun): Promise<void> { setSelected(run); setTradesLoading(true); setLoadError(""); try { const [detail, detailTrades] = await Promise.all([getBacktest(run.id), getBacktestTrades(run.id)]); setSelected(detail); setTrades(detailTrades); } catch { setLoadError("Unable to load this run's details."); } finally { setTradesLoading(false); } }
  async function created(run: BacktestRun): Promise<void> { setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]); await selectRun(run); }
  async function refresh(): Promise<void> { try { setRuns(await listBacktests()); setLoadError(""); } catch { setLoadError("Unable to refresh backtests."); } }
  return <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8"><div className="mx-auto max-w-7xl"><header className="mb-atlas-8 flex flex-col gap-atlas-4 border-b border-atlas-border pb-atlas-6 sm:flex-row sm:items-end sm:justify-between"><div><p className="font-atlas-mono text-atlas-xs leading-atlas-snug text-atlas-accent">HISTORICAL REPLAY</p><h1 className="mt-atlas-2 text-atlas-3xl font-atlas-semibold leading-atlas-tight tracking-atlas-tight text-atlas-fg">Backtests</h1><p className="mt-atlas-2 max-w-2xl text-atlas-md leading-atlas-normal text-atlas-fg-secondary">Test a registered strategy against persisted market data. Results are facts from the API, not recalculated in the browser.</p></div><button onClick={refresh} className="min-h-atlas-10 rounded-atlas border border-atlas-border px-atlas-4 py-atlas-2 text-atlas-md font-atlas-semibold leading-atlas-normal text-atlas-fg transition-colors duration-atlas-base ease-atlas-out hover:bg-atlas-bg-elevated focus:outline-none focus:ring-2 focus:ring-atlas-accent/30">Refresh runs</button></header>{loadError && <div className="mb-atlas-5 flex items-center gap-atlas-3 rounded-atlas bg-atlas-negative-dim p-atlas-4 text-atlas-md leading-atlas-normal text-atlas-negative" role="alert"><AlertCircle className="size-4" aria-hidden="true" />{loadError}</div>}<div className="grid gap-atlas-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]"><div className="order-2 lg:order-1">{selected ? <RunDetail run={selected} trades={trades} loading={tradesLoading} onBack={() => setSelected(null)} /> : <RunList runs={runs} selected={null} onSelect={selectRun} />}</div><div className="order-1 lg:order-2"><RunForm onCreated={created} /></div></div></div></main>;
}
