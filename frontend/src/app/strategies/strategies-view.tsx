"use client";

import axios from "axios";
import { AlertCircle, CheckCircle2, CirclePause, Loader2, Pencil, Play, RotateCcw, Square, WifiOff } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { BotForm } from "@/app/strategies/bot-form";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusBadge } from "@/components/ui/status-badge";
import { commandBot, createBot, getAccountSummary, isSupportedBotMode, listBots, listScopedBots, listStrategies, updateBot } from "@/lib/api";
import type { Bot, BotCommand, BotCreateRequest, BotMode, BotUpdateRequest, Strategy } from "@/lib/api";

const POLL_MS = 15_000;
type Mode = BotMode;

function formatDate(value: string | null): string {
  return value ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value)) : "—";
}

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === "string") return error.response.data.detail;
  return "The Atlas API did not confirm this operation.";
}

function statusTone(status: string): "connected" | "stale" | "disconnected" | "unavailable" {
  if (status === "running") return "connected";
  if (["starting", "stopping", "pausing", "paused"].includes(status)) return "stale";
  if (["error", "stopped"].includes(status)) return "disconnected";
  return "unavailable";
}

function statusIcon(status: string): React.ReactElement {
  if (status === "running") return <CheckCircle2 className="size-3" aria-hidden="true" />;
  if (["starting", "stopping", "pausing"].includes(status)) return <Loader2 className="size-3 animate-spin" aria-hidden="true" />;
  if (status === "error") return <AlertCircle className="size-3" aria-hidden="true" />;
  return <CirclePause className="size-3" aria-hidden="true" />;
}

function commandLabel(command: BotCommand): string {
  return command[0].toUpperCase() + command.slice(1);
}

function BotRow({ bot, accountId, onEdit, onCommand }: { bot: Bot; accountId: string; onEdit: (bot: Bot) => void; onCommand: (bot: Bot, command: BotCommand) => void }): React.ReactElement {
  const supportedMode = isSupportedBotMode(bot.mode);
  const canEdit = supportedMode && bot.status === "stopped";
  const commands: BotCommand[] = supportedMode ? (bot.status === "running" ? ["pause", "stop"] : bot.status === "paused" ? ["resume", "stop"] : bot.status === "stopped" ? ["start"] : []) : [];
  return <li className="grid gap-atlas-4 px-atlas-5 py-atlas-5 lg:grid-cols-[minmax(14rem,1.5fr)_minmax(14rem,1fr)_auto] lg:items-center">
    <div><div className="flex flex-wrap items-center gap-atlas-3"><h3 className="font-atlas-semibold">{bot.name}</h3><StatusBadge status={statusTone(bot.status)} label={bot.status} icon={statusIcon(bot.status)} /></div><p className="mt-atlas-2 text-atlas-xs text-atlas-fg-secondary">{bot.instrument} · {bot.timeframe} · account {accountId.slice(0, 8)}…</p><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">Observed {bot.status}; desired {bot.desired_status} · updated {formatDate(bot.updated_at)} UTC</p>{bot.last_error ? <p className="mt-atlas-1 text-atlas-xs text-atlas-negative">{bot.last_error}</p> : null}</div>
    <div className="text-atlas-sm"><p><span className="text-atlas-fg-secondary">Mode</span> {bot.mode}</p><p className="mt-atlas-1"><span className="text-atlas-fg-secondary">Strategy version</span> <span className="font-atlas-mono">{bot.strategy_version_id?.slice(0, 8) ?? "—"}…</span></p></div>
    <div className="flex flex-wrap justify-start gap-atlas-2 lg:justify-end">{supportedMode ? <><Button type="button" variant="ghost" onClick={() => onEdit(bot)} disabled={!canEdit} aria-label={canEdit ? `Edit ${bot.name}` : `Stop ${bot.name} before editing`}><Pencil className="size-4" aria-hidden="true" />Edit</Button>{commands.map((command) => <Button key={command} type="button" variant={command === "stop" ? "outline" : "default"} onClick={() => onCommand(bot, command)}><span className="sr-only">{commandLabel(command)} </span>{command === "start" || command === "resume" ? <Play className="size-4" aria-hidden="true" /> : command === "pause" ? <CirclePause className="size-4" aria-hidden="true" /> : <Square className="size-4" aria-hidden="true" />}{commandLabel(command)}</Button>)}</> : <span className="text-atlas-xs text-atlas-warn">Unsupported mode · controls unavailable</span>}</div>
  </li>;
}

export function StrategiesView({ mode }: { mode?: Mode }): React.ReactElement {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Bot | "new" | null>(null);
  const [confirmation, setConfirmation] = useState<{ bot: Bot; command: BotCommand } | null>(null);
  const [now, setNow] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(timer);
  }, []);
  const account = useQuery({ queryKey: ["account"], queryFn: getAccountSummary, refetchInterval: POLL_MS });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: listStrategies, refetchInterval: 60_000 });
  const bots = useQuery({ queryKey: ["bots", mode ?? "all", account.data?.account.id], queryFn: () => mode && account.data ? listScopedBots(account.data.account.id, mode) : listBots(), enabled: !mode || Boolean(account.data), refetchInterval: POLL_MS, refetchOnWindowFocus: true });
  const mutation = useMutation({ mutationFn: ({ bot, command }: { bot: Bot; command: BotCommand }) => { if (!isSupportedBotMode(bot.mode)) throw new Error("This bot has an unsupported execution mode."); return commandBot(bot.id, command, { account_id: bot.account_id, mode: bot.mode }); }, onSuccess: async (bot) => { await Promise.all([queryClient.invalidateQueries({ queryKey: ["bots"] }), queryClient.invalidateQueries({ queryKey: ["dashboard"] })]); await queryClient.refetchQueries({ queryKey: ["bots"] }); toast.success(`Bot ${bot.name} acknowledged ${bot.desired_status}`); setConfirmation(null); }, onError: (error) => toast.error("Bot command failed", { description: errorMessage(error) }) });
  const saveMutation = useMutation({ mutationFn: ({ bot, request }: { bot: Bot | undefined; request: BotCreateRequest | BotUpdateRequest }) => { if (bot) return updateBot(bot.id, request); if ("account_id" in request) return createBot(request); throw new Error("A bot account scope is required."); }, onSuccess: (bot) => { queryClient.invalidateQueries({ queryKey: ["bots"] }); toast.success(bot.name + (editing === "new" ? " created stopped" : " configuration saved")); setEditing(null); }, onError: (error) => toast.error("Unable to save bot", { description: errorMessage(error) }) });
  const visibleStrategies = useMemo(() => strategies.data ?? [], [strategies.data]);

  if (strategies.isPending || (mode && account.isPending)) return <main className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12" role="status"><Loader2 className="mr-atlas-2 inline size-4 animate-spin" aria-hidden="true" />Loading operational data…</main>;
  if (strategies.isError || (bots.isError && !bots.data) || (mode && account.isError && !account.data)) return <main className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12"><section className="rounded-atlas-md border border-atlas-border bg-atlas-bg-elevated p-atlas-6" role="alert"><WifiOff className="size-5 text-atlas-negative" aria-hidden="true" /><h1 className="mt-atlas-3 text-atlas-xl font-atlas-semibold">Operational data unavailable</h1><p className="mt-atlas-2 text-atlas-sm text-atlas-fg-secondary">REST polling could not load this {mode ?? "strategy"} view. No bot state has been inferred.</p><Button className="mt-atlas-4" variant="outline" onClick={() => { void strategies.refetch(); void bots.refetch(); }}>Try again</Button></section></main>;

  const botData = bots.data ?? [];
  const accountId = account.data?.account.id ?? botData[0]?.account_id ?? "";
  const stale = now > 0 && bots.dataUpdatedAt > 0 && now - bots.dataUpdatedAt > POLL_MS * 2;
  const disconnected = bots.isError;
  return <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8"><div className="mx-auto max-w-atlas"><header className="mb-atlas-8 flex flex-col gap-atlas-4 border-b border-atlas-border pb-atlas-6 sm:flex-row sm:items-end sm:justify-between"><div><p className="font-atlas-mono text-atlas-xs tracking-atlas-wide text-atlas-accent">OPERATIONS · {mode ? mode.toUpperCase() : "STRATEGIES"}</p><h1 className="mt-atlas-2 text-atlas-3xl font-atlas-semibold tracking-atlas-tight">{mode ? `${mode === "paper" ? "Paper trading" : "Testnet"}` : "Strategies"}</h1><p className="mt-atlas-2 text-atlas-md text-atlas-fg-secondary">{mode ? `Monitor ${mode} bots from authoritative REST snapshots.` : "Review deployed strategy identities and control configured bots."}</p></div><div className="flex items-center gap-atlas-3"><StatusBadge status={disconnected ? "disconnected" : stale ? "stale" : "connected"} label={disconnected ? "REST disconnected" : stale ? "Data stale" : bots.isFetching ? "REST polling…" : "REST polling"} icon={disconnected ? <WifiOff className="size-3" aria-hidden="true" /> : stale ? <AlertCircle className="size-3" aria-hidden="true" /> : <CheckCircle2 className="size-3" aria-hidden="true" />} /><Button onClick={() => setEditing("new")} disabled={!accountId || visibleStrategies.every((strategy) => strategy.versions.length === 0)}>Create bot</Button></div></header>
    {stale ? <div className="mb-atlas-5 rounded-atlas border border-atlas-border bg-atlas-warn-dim p-atlas-3 text-atlas-sm text-atlas-warn" role="status">The last successful bot refresh is older than the polling window. Retrying REST reads.</div> : null}
    {editing ? <div className="mb-atlas-6"><BotForm accountId={accountId} strategies={visibleStrategies} mode={mode} bot={editing === "new" ? undefined : editing} busy={saveMutation.isPending} onCancel={() => setEditing(null)} onSubmit={(request) => saveMutation.mutate({ bot: editing === "new" ? undefined : editing, request })} /></div> : null}
    {!mode ? <section className="rounded-atlas-md border border-atlas-border bg-atlas-surface"><div className="border-b border-atlas-border px-atlas-5 py-atlas-4"><h2 className="text-atlas-lg font-atlas-semibold">Deployed strategy versions · {visibleStrategies.length}</h2></div><div className="divide-y divide-atlas-border">{visibleStrategies.length === 0 ? <p className="p-atlas-5 text-atlas-sm text-atlas-fg-secondary">No deployed strategy versions are available.</p> : visibleStrategies.map((strategy: Strategy) => <div key={strategy.id} className="px-atlas-5 py-atlas-4"><div className="flex flex-wrap items-center justify-between gap-atlas-3"><div><h3 className="font-atlas-semibold">{strategy.name} <span className="text-atlas-fg-secondary">v{strategy.version}</span></h3><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">Commit <span className="font-atlas-mono">{strategy.commit_sha}</span> · {strategy.versions.length} deployed version{strategy.versions.length === 1 ? "" : "s"}</p></div><span className="text-atlas-xs text-atlas-fg-secondary">Created {formatDate(strategy.created_at)} UTC</span></div></div>)}</div></section> : null}
    <section className="mt-atlas-6 overflow-hidden rounded-atlas-md border border-atlas-border bg-atlas-surface"><div className="flex items-center justify-between border-b border-atlas-border px-atlas-5 py-atlas-4"><h2 className="text-atlas-lg font-atlas-semibold">Bots · {botData.length}</h2><span className="text-atlas-xs text-atlas-fg-secondary">Last successful refresh {formatDate(new Date(bots.dataUpdatedAt).toISOString())} UTC</span></div>{botData.length === 0 ? <p className="px-atlas-5 py-atlas-8 text-atlas-sm text-atlas-fg-secondary">No {mode ?? "configured"} bots are available in this scope.</p> : <ul className="divide-y divide-atlas-border">{botData.map((bot) => <BotRow key={bot.id} bot={bot} accountId={bot.account_id} onEdit={setEditing} onCommand={(selectedBot, command) => setConfirmation({ bot: selectedBot, command })} />)}</ul>}</section>
    <p className="mt-atlas-5 text-atlas-xs text-atlas-fg-secondary">Observed and desired lifecycle state comes from FastAPI. Decimal P&amp;L values are displayed as received. Polling is authoritative; stale or disconnected reads never claim a lifecycle transition succeeded.</p>
  </div><ConfirmDialog open={Boolean(confirmation)} title={`${confirmation ? commandLabel(confirmation.command) : "Confirm"} bot?`} details={confirmation ? [`Bot: ${confirmation.bot.name}`, `Account: ${confirmation.bot.account_id}`, `Mode: ${confirmation.bot.mode}`, `Instrument: ${confirmation.bot.instrument}`, `Observed: ${confirmation.bot.status} · desired: ${confirmation.bot.desired_status}`] : []} consequence={confirmation ? `This will request ${confirmation.command} for this bot. The API response and next REST refresh remain authoritative; no running or stopped state is assumed before confirmation.` : ""} confirmLabel={confirmation ? commandLabel(confirmation.command) : "Confirm"} busy={mutation.isPending} onCancel={() => setConfirmation(null)} onConfirm={() => { if (confirmation) mutation.mutate(confirmation); }} /></main>;
}
