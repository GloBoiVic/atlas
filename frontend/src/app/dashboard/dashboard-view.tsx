"use client";

import axios from "axios";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Loader2,
  RefreshCw,
  Server,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  getAnalytics,
  getDashboardSummary,
  getHealth,
  listStrategies,
} from "@/lib/api";
import type { DashboardSummary } from "@/lib/api";

const POLL_MS = 15_000;

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatMoney(value: string | null): string {
  return value === null ? "—" : `$${value}`;
}

function pnlTone(value: string | null): string {
  return value?.startsWith("-") ? "text-atlas-negative" : "text-atlas-positive";
}

function statusTone(status: string): "connected" | "stale" | "disconnected" | "unavailable" {
  if (["running", "connected", "ok", "active"].includes(status.toLowerCase())) return "connected";
  if (["starting", "stopping", "pending", "paused"].includes(status.toLowerCase())) return "stale";
  if (["error", "failed", "disconnected", "stopped"].includes(status.toLowerCase())) return "disconnected";
  return "unavailable";
}

function ErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }): React.ReactElement {
  const detail = axios.isAxiosError(error) && typeof error.response?.data?.detail === "string"
    ? error.response.data.detail
    : "The Atlas API did not return this read model.";
  const unavailable = axios.isAxiosError(error) && error.response?.status === 503;
  return (
    <section className="rounded-atlas-md border border-atlas-border bg-atlas-bg-elevated p-atlas-6" role="alert">
      <div className="flex items-start gap-atlas-3">
        <AlertCircle className="mt-0.5 size-5 shrink-0 text-atlas-warn" aria-hidden="true" />
        <div>
          <h2 className="text-atlas-lg font-atlas-semibold">{unavailable ? "Data unavailable" : "Unable to load dashboard"}</h2>
          <p className="mt-atlas-2 text-atlas-sm text-atlas-fg-secondary">{detail}</p>
          <Button className="mt-atlas-4" variant="outline" onClick={onRetry}>Try again</Button>
        </div>
      </div>
    </section>
  );
}

function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }): React.ReactElement {
  return (
    <section className={`overflow-hidden rounded-atlas-md border border-atlas-border bg-atlas-surface ${className}`}>
      <div className="flex items-center justify-between border-b border-atlas-border px-atlas-5 py-atlas-4">
        <h2 className="text-atlas-lg font-atlas-semibold">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function AccountPanel({ summary }: { summary: DashboardSummary["account"] }): React.ReactElement {
  const metrics = [
    ["Equity", formatMoney(summary.equity), "text-atlas-fg"],
    ["Starting equity", formatMoney(summary.starting_equity), "text-atlas-fg"],
    ["Realized P&L", formatMoney(summary.realized_pnl), pnlTone(summary.realized_pnl)],
    ["Unrealized P&L", formatMoney(summary.unrealized_pnl), pnlTone(summary.unrealized_pnl)],
  ];
  return (
    <Panel title="Account overview">
      <div className="grid gap-atlas-5 p-atlas-5 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map(([label, value, tone]) => (
          <div key={label}>
            <p className="text-atlas-xs text-atlas-fg-secondary">{label}</p>
            <p className={`mt-atlas-2 font-atlas-mono text-atlas-xl ${tone}`}>{value}</p>
          </div>
        ))}
      </div>
      <div className="border-t border-atlas-border px-atlas-5 py-atlas-3 text-atlas-xs text-atlas-fg-secondary">
        {summary.account.name} · {summary.account.broker} · {summary.account.mode} · As of {formatDate(summary.as_of)} UTC
      </div>
    </Panel>
  );
}

function PositionsPanel({ positions }: { positions: DashboardSummary["positions"] }): React.ReactElement {
  return (
    <Panel title={`Open positions · ${positions.length}`}>
      {positions.length === 0 ? <EmptyState text="No open positions in this account and mode." /> : (
        <div className="overflow-x-auto"><table className="w-full text-left text-atlas-sm"><thead className="text-atlas-xs text-atlas-fg-secondary"><tr><th className="px-atlas-5 py-atlas-3 font-normal">Symbol</th><th className="px-atlas-5 py-atlas-3 font-normal">Side / quantity</th><th className="px-atlas-5 py-atlas-3 font-normal">Entry</th><th className="px-atlas-5 py-atlas-3 text-right font-normal">Unrealized P&L</th><th className="px-atlas-5 py-atlas-3 font-normal">Opened (UTC)</th></tr></thead><tbody>{positions.map((position) => <tr key={position.id} className="border-t border-atlas-border"><th scope="row" className="px-atlas-5 py-atlas-4 font-atlas-semibold">{position.symbol}</th><td className="px-atlas-5 py-atlas-4">{position.side} · <span className="font-atlas-mono">{position.quantity}</span></td><td className="px-atlas-5 py-atlas-4 font-atlas-mono">{position.entry_price}</td><td className={`px-atlas-5 py-atlas-4 text-right font-atlas-mono ${pnlTone(position.unrealized_pnl)}`}>{formatMoney(position.unrealized_pnl)}</td><td className="whitespace-nowrap px-atlas-5 py-atlas-4 text-atlas-fg-secondary">{formatDate(position.opened_at)}</td></tr>)}</tbody></table></div>
      )}
    </Panel>
  );
}

function EmptyState({ text }: { text: string }): React.ReactElement {
  return <p className="px-atlas-5 py-atlas-8 text-atlas-sm text-atlas-fg-secondary">{text}</p>;
}

function BotsPanel({ bots }: { bots: DashboardSummary["bots"] }): React.ReactElement {
  return <Panel title={`Bots · ${bots.length}`}>
    {bots.length === 0 ? <EmptyState text="No bots are configured for this account and mode." /> : <ul className="divide-y divide-atlas-border">{bots.map((bot) => <li key={bot.id} className="flex flex-wrap items-center justify-between gap-atlas-3 px-atlas-5 py-atlas-4"><div><p className="font-atlas-semibold">{bot.name}</p><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">{bot.instrument} · {bot.timeframe} · {bot.mode}</p>{bot.last_error ? <p className="mt-atlas-1 text-atlas-xs text-atlas-negative">{bot.last_error}</p> : null}</div><div className="flex items-center gap-atlas-3"><StatusBadge status={statusTone(bot.status)} label={bot.status} /><span className={`font-atlas-mono text-atlas-sm ${pnlTone(bot.pnl)}`}>{formatMoney(bot.pnl)}</span></div></li>)}</ul>}
  </Panel>;
}

function TradesPanel({ trades }: { trades: DashboardSummary["recent_trades"] }): React.ReactElement {
  return <Panel title="Recent trades"><div className="divide-y divide-atlas-border">{trades.length === 0 ? <EmptyState text="No trades have been recorded for this account and mode." /> : trades.map((trade) => <div key={trade.id} className="flex flex-wrap items-center justify-between gap-atlas-3 px-atlas-5 py-atlas-4"><div><p className="font-atlas-semibold">{trade.symbol} <span className="text-atlas-fg-secondary">· {trade.direction}</span></p><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">{trade.status} · {formatDate(trade.exit_time ?? trade.entry_time)} UTC</p></div><span className={`font-atlas-mono text-atlas-sm ${pnlTone(trade.net_pnl)}`}>{formatMoney(trade.net_pnl)}</span></div>)}</div></Panel>;
}

export function DashboardView(): React.ReactElement {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(timer);
  }, []);
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: getDashboardSummary, refetchInterval: POLL_MS, refetchOnWindowFocus: true });
  const analytics = useQuery({ queryKey: ["analytics", "dashboard"], queryFn: () => getAnalytics(), refetchInterval: POLL_MS, refetchOnWindowFocus: true });
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 30_000, refetchOnWindowFocus: true });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: listStrategies, refetchInterval: 60_000 });

  if (dashboard.isPending) return <main className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12" role="status"><div className="flex items-center gap-atlas-3 text-atlas-sm text-atlas-fg-secondary"><Loader2 className="size-4 animate-spin" aria-hidden="true" />Loading operational data…</div></main>;
  if (dashboard.isError) return <main className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12"><ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} /></main>;

  const stale = now > 0 && dashboard.dataUpdatedAt > 0 && now - dashboard.dataUpdatedAt > POLL_MS * 2;
  return <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8"><div className="mx-auto max-w-atlas">
    <header className="mb-atlas-8 flex flex-col gap-atlas-4 border-b border-atlas-border pb-atlas-6 sm:flex-row sm:items-end sm:justify-between"><div><p className="font-atlas-mono text-atlas-xs tracking-atlas-wide text-atlas-accent">OPERATIONS · {dashboard.data.account.account.mode.toUpperCase()}</p><h1 className="mt-atlas-2 text-atlas-3xl font-atlas-semibold tracking-atlas-tight">Dashboard</h1><p className="mt-atlas-2 text-atlas-md text-atlas-fg-secondary">How is automated trading doing right now?</p></div><div className="flex flex-wrap items-center gap-atlas-3"><StatusBadge status={health.isError ? "disconnected" : stale ? "stale" : "connected"} label={health.isError ? "API disconnected" : stale ? "Data stale" : "REST polling"} icon={health.isError ? <Server className="size-3" aria-hidden="true" /> : stale ? <Clock3 className="size-3" aria-hidden="true" /> : <CheckCircle2 className="size-3" aria-hidden="true" />} /><Button variant="outline" onClick={() => void dashboard.refetch()} disabled={dashboard.isFetching}><RefreshCw className={`size-4 ${dashboard.isFetching ? "animate-spin" : ""}`} aria-hidden="true" />Refresh</Button></div></header>
    {stale ? <div className="mb-atlas-5 flex items-center gap-atlas-3 rounded-atlas border border-atlas-border bg-atlas-warn-dim p-atlas-3 text-atlas-sm text-atlas-warn" role="status"><Clock3 className="size-4" aria-hidden="true" />The last dashboard snapshot is older than the polling interval. Retrying REST reads.</div> : null}
    <AccountPanel summary={dashboard.data.account} />
    <div className="mt-atlas-6 grid gap-atlas-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(300px,1fr)]"><PositionsPanel positions={dashboard.data.positions} /><BotsPanel bots={dashboard.data.bots} /></div>
    <div className="mt-atlas-6 grid gap-atlas-6 lg:grid-cols-2"><TradesPanel trades={dashboard.data.recent_trades} /><Panel title="Analytics snapshot">{analytics.isPending ? <EmptyState text="Loading API-provided analytics…" /> : analytics.isError ? <EmptyState text="Analytics is unavailable for this deployment or account scope." /> : <div className="grid gap-atlas-4 p-atlas-5 sm:grid-cols-2"><div><p className="text-atlas-xs text-atlas-fg-secondary">Total return</p><p className={`mt-atlas-2 font-atlas-mono text-atlas-xl ${pnlTone(analytics.data.total_return)}`}>{analytics.data.total_return}</p></div><div><p className="text-atlas-xs text-atlas-fg-secondary">Ending equity</p><p className="mt-atlas-2 font-atlas-mono text-atlas-xl">{formatMoney(analytics.data.ending_equity)}</p></div><div className="sm:col-span-2"><p className="text-atlas-xs text-atlas-fg-secondary">Equity curve</p><p className="mt-atlas-2 text-atlas-sm text-atlas-fg-secondary">{analytics.data.equity_curve.length} API-provided UTC points · {analytics.data.total_trades} closed trades</p></div></div>}</Panel></div>
    <p className="mt-atlas-6 text-atlas-xs text-atlas-fg-secondary">Updated {formatDate(new Date(dashboard.dataUpdatedAt).toISOString())} UTC · {strategies.isSuccess ? `${strategies.data.length} deployed strateg${strategies.data.length === 1 ? "y" : "ies"}` : "Strategy inventory unavailable"} · REST polling every 15 seconds</p>
  </div></main>;
}
