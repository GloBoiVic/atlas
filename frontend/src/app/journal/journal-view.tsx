"use client";

import { FormEvent, ReactElement, useState } from "react";
import axios from "axios";
import { AlertCircle, BookOpen, ChevronDown, Loader2, RefreshCw, SearchX } from "lucide-react";
import { toast } from "sonner";

import { JournalEntry, listJournalEntries, updateJournalNotes } from "@/lib/api";

const panelClass = "rounded-atlas-md border border-atlas-border bg-atlas-surface";
const inputClass =
  "w-full rounded-atlas border border-atlas-border bg-atlas-bg-elevated px-atlas-3 py-[10px] text-atlas-md leading-atlas-normal text-atlas-fg outline-none transition-colors duration-atlas-base ease-atlas-out placeholder:text-atlas-fg-secondary focus:border-atlas-accent focus:ring-2 focus:ring-atlas-accent/20";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatContext(value: Record<string, unknown>): string {
  const content = JSON.stringify(value);
  return content === "{}" ? "No context recorded" : content;
}

function PnlValue({ pnl }: { pnl: string | null }): ReactElement {
  if (pnl === null) return <span className="font-atlas-mono text-atlas-fg-secondary">—</span>;
  const positive = !pnl.startsWith("-") && pnl !== "0" && pnl !== "0.0";
  const tone = positive
    ? "text-atlas-positive"
    : pnl.startsWith("-")
      ? "text-atlas-negative"
      : "text-atlas-fg";
  return <span className={`font-atlas-mono ${tone}`}>{positive ? "+" : ""}{pnl}</span>;
}

function JournalRow({
  entry,
  onSaved,
}: {
  entry: JournalEntry;
  onSaved: (entry: JournalEntry) => void;
}): ReactElement {
  const [notes, setNotes] = useState(entry.notes ?? "");
  const [saving, setSaving] = useState(false);
  const changed = notes !== (entry.notes ?? "");

  async function saveNotes(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    try {
      const saved = await updateJournalNotes(entry.id, { notes: notes.trim() || null });
      setNotes(saved.notes ?? "");
      onSaved(saved);
      toast.success("Journal note saved");
    } catch (cause) {
      const detail = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
      toast.error(typeof detail === "string" ? detail : "Unable to save this note.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <article
      className="border-b border-atlas-border px-atlas-5 py-atlas-5 last:border-b-0 sm:px-atlas-6"
      aria-label={`${entry.symbol} journal entry`}
    >
      <div className="grid gap-atlas-4 lg:grid-cols-[1.5fr_1fr_1fr_1fr_auto] lg:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-atlas-2">
            <h3 className="text-atlas-md font-atlas-semibold text-atlas-fg">{entry.symbol}</h3>
            <span
              className={`rounded-atlas-pill px-atlas-2 py-atlas-1 text-atlas-xs font-atlas-semibold ${entry.direction === "long" ? "bg-atlas-positive-dim text-atlas-positive" : "bg-atlas-negative-dim text-atlas-negative"}`}
            >
              {entry.direction}
            </span>
          </div>
          <p className="mt-atlas-1 truncate text-atlas-sm text-atlas-fg-secondary">{entry.strategy_name}</p>
          <p className="mt-atlas-1 font-atlas-mono text-atlas-xs text-atlas-fg-secondary">
            {entry.trade_id.slice(0, 8)}…
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-x-atlas-4 gap-y-atlas-2 text-atlas-sm sm:grid-cols-3 lg:grid-cols-2">
          <div><dt className="text-atlas-xs text-atlas-fg-secondary">Entry</dt><dd className="font-atlas-mono text-atlas-fg">{entry.entry_price}</dd></div>
          <div><dt className="text-atlas-xs text-atlas-fg-secondary">Exit</dt><dd className="font-atlas-mono text-atlas-fg">{entry.exit_price ?? "—"}</dd></div>
          <div><dt className="text-atlas-xs text-atlas-fg-secondary">Quantity</dt><dd className="font-atlas-mono text-atlas-fg">{entry.quantity}</dd></div>
        </dl>

        <div><p className="text-atlas-xs text-atlas-fg-secondary">P&L</p><p className="mt-atlas-1 text-atlas-lg"><PnlValue pnl={entry.pnl} /></p></div>
        <div className="text-atlas-sm text-atlas-fg-secondary"><p>Opened {formatDate(entry.opened_at)}</p><p className="mt-atlas-1">Closed {formatDate(entry.closed_at)}</p></div>

        <details className="group lg:justify-self-end">
          <summary className="flex min-h-atlas-10 cursor-pointer list-none items-center gap-atlas-2 rounded-atlas px-atlas-3 py-atlas-2 text-atlas-sm font-atlas-semibold text-atlas-fg-secondary hover:bg-atlas-bg-elevated focus:outline-none focus:ring-2 focus:ring-atlas-accent/30 [&::-webkit-details-marker]:hidden">
            Context <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden="true" />
          </summary>
          <div className="mt-atlas-3 space-y-atlas-3 rounded-atlas border border-atlas-border bg-atlas-bg-elevated p-atlas-3 text-atlas-xs text-atlas-fg-secondary lg:absolute lg:mr-atlas-6 lg:w-96">
            <div><p className="font-atlas-semibold text-atlas-fg">Signal</p><pre className="mt-atlas-1 whitespace-pre-wrap break-words font-atlas-mono leading-atlas-normal">{formatContext(entry.signal)}</pre></div>
            <div><p className="font-atlas-semibold text-atlas-fg">Market conditions</p><pre className="mt-atlas-1 whitespace-pre-wrap break-words font-atlas-mono leading-atlas-normal">{formatContext(entry.market_conditions)}</pre></div>
          </div>
        </details>
      </div>

      <form className="mt-atlas-5 border-t border-atlas-border pt-atlas-4" onSubmit={saveNotes}>
        <label htmlFor={`notes-${entry.id}`} className="text-atlas-sm font-atlas-semibold text-atlas-fg">
          Notes <span className="font-atlas-regular text-atlas-fg-secondary">(your reflection)</span>
        </label>
        <div className="mt-atlas-2 flex flex-col gap-atlas-3 sm:flex-row sm:items-end">
          <textarea
            id={`notes-${entry.id}`}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            maxLength={10000}
            rows={2}
            placeholder="What did you learn from this trade?"
            className={`${inputClass} min-h-20 resize-y sm:flex-1`}
          />
          <button
            type="submit"
            disabled={!changed || saving}
            className="inline-flex min-h-atlas-10 shrink-0 items-center justify-center gap-atlas-2 rounded-atlas bg-atlas-accent px-atlas-4 py-atlas-2 text-atlas-sm font-atlas-semibold text-white transition-colors duration-atlas-base ease-atlas-out hover:bg-atlas-accent-dim focus:outline-none focus:ring-2 focus:ring-atlas-accent/40 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {saving ? "Saving…" : "Save note"}
          </button>
        </div>
      </form>
    </article>
  );
}

export default function JournalView({
  initialEntries,
  initialLoadError,
}: {
  initialEntries: JournalEntry[];
  initialLoadError?: string;
}): ReactElement {
  const [entries, setEntries] = useState(initialEntries);
  const [error, setError] = useState(initialLoadError ?? "");
  const [refreshing, setRefreshing] = useState(false);

  async function refresh(): Promise<void> {
    setRefreshing(true);
    try {
      setEntries(await listJournalEntries());
      setError("");
    } catch {
      setError("Unable to refresh the journal. Check the API connection and try again.");
    } finally {
      setRefreshing(false);
    }
  }

  function replaceEntry(saved: JournalEntry): void {
    setEntries((current) => current.map((entry) => entry.id === saved.id ? saved : entry));
  }

  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-atlas-8 flex flex-col gap-atlas-4 border-b border-atlas-border pb-atlas-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-atlas-xs font-atlas-semibold text-atlas-accent">TRADE REFLECTION</p>
            <h1 className="mt-atlas-2 text-atlas-3xl font-atlas-semibold leading-atlas-tight tracking-atlas-tight text-atlas-fg">Journal</h1>
            <p className="mt-atlas-2 max-w-2xl text-atlas-md leading-atlas-normal text-atlas-fg-secondary">Review completed trades with the context that shaped each decision. Notes are yours; trade facts come from the API.</p>
          </div>
          <button type="button" onClick={refresh} disabled={refreshing} className="inline-flex min-h-atlas-10 items-center justify-center gap-atlas-2 rounded-atlas border border-atlas-border px-atlas-4 py-atlas-2 text-atlas-md font-atlas-semibold text-atlas-fg hover:bg-atlas-bg-elevated focus:outline-none focus:ring-2 focus:ring-atlas-accent/30 disabled:cursor-not-allowed disabled:opacity-60">
            {refreshing ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />} Refresh
          </button>
        </header>

        {error && <div className="mb-atlas-5 flex items-center gap-atlas-3 rounded-atlas bg-atlas-negative-dim p-atlas-4 text-atlas-md text-atlas-negative" role="alert"><AlertCircle className="size-4 shrink-0" aria-hidden="true" />{error}</div>}
        <section className={panelClass} aria-labelledby="journal-entries-heading">
          <div className="flex items-center justify-between border-b border-atlas-border px-atlas-5 py-atlas-4 sm:px-atlas-6"><div><h2 id="journal-entries-heading" className="text-atlas-lg font-atlas-semibold text-atlas-fg">Completed trades</h2><p className="mt-atlas-1 text-atlas-xs text-atlas-fg-secondary">{entries.length} {entries.length === 1 ? "entry" : "entries"} · immutable trade facts</p></div><BookOpen className="size-5 text-atlas-accent" aria-hidden="true" /></div>
          {entries.length === 0 ? <div className="flex flex-col items-center px-atlas-5 py-[56px] text-center"><SearchX className="size-7 text-atlas-fg-secondary" aria-hidden="true" /><p className="mt-atlas-3 text-atlas-lg font-atlas-semibold text-atlas-fg">No journal entries yet</p><p className="mt-atlas-1 max-w-md text-atlas-md text-atlas-fg-secondary">Completed trades will appear here with signal and market context when the journal projection is available.</p></div> : <div>{entries.map((entry) => <JournalRow key={entry.id} entry={entry} onSaved={replaceEntry} />)}</div>}
        </section>
      </div>
    </main>
  );
}
