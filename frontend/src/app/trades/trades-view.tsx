"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import { AlertCircle, CheckCircle2, Clock3, Loader2, RefreshCw, SearchX, Server } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { listTrades, type Trade } from "@/lib/api";

const POLL_MS = 15_000;

function formatUtc(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

function pnlTone(value: string | null): string {
  if (!value || /^-?0(?:\.0*)?$/.test(value)) return "text-atlas-fg";
  return value.startsWith("-") ? "text-atlas-negative" : "text-atlas-positive";
}

function PnlValue({ value }: { value: string | null }): React.ReactElement {
  if (value === null) return <span className="font-atlas-mono text-atlas-fg-secondary">—</span>;
  const prefix = value.startsWith("-") || /^0(?:\.0*)?$/.test(value) ? "" : "+";
  return <span className={`font-atlas-mono ${pnlTone(value)}`}>{prefix}{value}</span>;
}

function TradeRow({ trade }: { trade: Trade }): React.ReactElement {
  return (
    <tr className="border-t border-atlas-border align-top">
      <th scope="row" className="whitespace-nowrap px-atlas-5 py-atlas-4 text-left font-atlas-semibold">
        <span>{trade.symbol}</span>
        <span className="mt-atlas-1 block text-atlas-xs font-atlas-regular text-atlas-fg-secondary">{trade.direction} · {trade.mode}</span>
      </th>
      <td className="px-atlas-5 py-atlas-4"><span className="font-atlas-mono">{trade.entry_price}</span><span className="mt-atlas-1 block text-atlas-xs text-atlas-fg-secondary">{formatUtc(trade.entry_time)} UTC</span></td>
      <td className="px-atlas-5 py-atlas-4"><span className="font-atlas-mono">{trade.exit_price ?? "—"}</span><span className="mt-atlas-1 block text-atlas-xs text-atlas-fg-secondary">{formatUtc(trade.exit_time)} UTC</span></td>
      <td className="px-atlas-5 py-atlas-4 font-atlas-mono">{trade.quantity}</td>
      <td className="px-atlas-5 py-atlas-4"><PnlValue value={trade.net_pnl} /><span className="mt-atlas-1 block text-atlas-xs text-atlas-fg-secondary">Gross {trade.gross_pnl ?? "—"}</span></td>
      <td className="px-atlas-5 py-atlas-4"><span className="rounded-atlas-pill bg-atlas-bg-elevated px-atlas-2 py-atlas-1 text-atlas-xs text-atlas-fg-secondary">{trade.status}</span><span className="mt-atlas-2 block text-atlas-xs text-atlas-fg-secondary">Fees {trade.total_fees}</span></td>
    </tr>
  );
}

function ErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }): React.ReactElement {
  const detail = axios.isAxiosError(error) && typeof error.response?.data?.detail === "string"
    ? error.response.data.detail
    : "The Atlas API did not return trade history.";
  return (
    <section className="rounded-atlas-md border border-atlas-border bg-atlas-bg-elevated p-atlas-6" role="alert">
      <div className="flex items-start gap-atlas-3"><AlertCircle className="mt-0.5 size-5 shrink-0 text-atlas-negative" aria-hidden="true" /><div><h2 className="text-atlas-lg font-atlas-semibold">Trade history disconnected</h2><p className="mt-atlas-2 text-atlas-sm text-atlas-fg-secondary">{detail}</p><Button className="mt-atlas-4" variant="outline" onClick={onRetry}>Try again</Button></div></div>
    </section>
  );
}

export function TradesView(): React.ReactElement {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(timer);
  }, []);

  const trades = useQuery({
    queryKey: ["trades"],
    queryFn: () => listTrades(100),
    refetchInterval: POLL_MS,
    refetchOnWindowFocus: true,
  });
  const stale = now > 0 && trades.dataUpdatedAt > 0 && now - trades.dataUpdatedAt > POLL_MS * 2;

  if (trades.isPending) return <main className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12" role="status"><div className="flex items-center gap-atlas-3 text-atlas-sm text-atlas-fg-secondary"><Loader2 className="size-4 animate-spin" aria-hidden="true" />Loading trade history…</div></main>;
  if (trades.isError) return <main className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12"><ErrorState error={trades.error} onRetry={() => void trades.refetch()} /></main>;

  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-atlas">
        <header className="mb-atlas-8 flex flex-col gap-atlas-4 border-b border-atlas-border pb-atlas-6 sm:flex-row sm:items-end sm:justify-between"><div><p className="font-atlas-mono text-atlas-xs tracking-atlas-wide text-atlas-accent">EXECUTION HISTORY</p><h1 className="mt-atlas-2 text-atlas-3xl font-atlas-semibold tracking-atlas-tight">Trades</h1><p className="mt-atlas-2 max-w-2xl text-atlas-md text-atlas-fg-secondary">Review API-recorded executions across the configured account scope. Monetary and quantity values remain Decimal strings.</p></div><div className="flex flex-wrap items-center gap-atlas-3"><StatusBadge status={stale ? "stale" : "connected"} label={stale ? "Data stale" : "REST polling"} icon={stale ? <Clock3 className="size-3" aria-hidden="true" /> : <CheckCircle2 className="size-3" aria-hidden="true" />} /><Button variant="outline" onClick={() => void trades.refetch()} disabled={trades.isFetching}><RefreshCw className={`size-4 ${trades.isFetching ? "animate-spin" : ""}`} aria-hidden="true" />Refresh</Button></div></header>
        {stale ? <div className="mb-atlas-5 flex items-center gap-atlas-3 rounded-atlas border border-atlas-border bg-atlas-warn-dim p-atlas-3 text-atlas-sm text-atlas-warn" role="status"><Clock3 className="size-4" aria-hidden="true" />Trade history is older than two polling intervals. Retrying REST reads.</div> : null}
        <section className="overflow-hidden rounded-atlas-md border border-atlas-border bg-atlas-surface" aria-labelledby="trade-history-heading"><div className="flex items-center justify-between border-b border-atlas-border px-atlas-5 py-atlas-4"><div><h2 id="trade-history-heading" className="text-atlas-lg font-atlas-semibold">Recorded trades</h2><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">{trades.data.length} {trades.data.length === 1 ? "trade" : "trades"} · timestamps shown in UTC</p></div><Server className="size-5 text-atlas-accent" aria-hidden="true" /></div>{trades.data.length === 0 ? <div className="flex flex-col items-center px-atlas-5 py-[56px] text-center"><SearchX className="size-7 text-atlas-fg-secondary" aria-hidden="true" /><h3 className="mt-atlas-3 text-atlas-lg font-atlas-semibold">No trades recorded yet</h3><p className="mt-atlas-1 max-w-md text-atlas-md text-atlas-fg-secondary">Completed execution facts will appear here when the scoped API read model has records.</p></div> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-atlas-sm"><caption className="sr-only">Trade history with entry and exit facts</caption><thead className="text-atlas-xs text-atlas-fg-secondary"><tr><th scope="col" className="px-atlas-5 py-atlas-3 font-normal">Instrument</th><th scope="col" className="px-atlas-5 py-atlas-3 font-normal">Entry</th><th scope="col" className="px-atlas-5 py-atlas-3 font-normal">Exit</th><th scope="col" className="px-atlas-5 py-atlas-3 font-normal">Quantity</th><th scope="col" className="px-atlas-5 py-atlas-3 font-normal">Net P&amp;L</th><th scope="col" className="px-atlas-5 py-atlas-3 font-normal">Status</th></tr></thead><tbody>{trades.data.map((trade) => <TradeRow key={trade.id} trade={trade} />)}</tbody></table></div>}</section><p className="mt-atlas-6 text-atlas-xs text-atlas-fg-secondary">Updated {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(trades.dataUpdatedAt))} UTC · REST polling every 15 seconds</p>
      </div>
    </main>
  );
}
