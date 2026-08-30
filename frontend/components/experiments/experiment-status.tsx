'use client';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import type { FormEvent, KeyboardEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, LoaderCircle, RefreshCw } from 'lucide-react';
import { AppShell } from '../app-shell';
import { Button } from '../ui/button';
import {
  ApiError,
  ApiTransportTimeoutError,
  atlasApi,
} from '../../lib/api-client';
import { useDisplayTimeZone } from '../../app/providers';
import { formatCurrency, formatPercent } from '../../lib/experiment-formatters';
import type { Json } from './shared';
import {
  object,
  text,
  strategyIdentity,
  statusOf,
  marketIdentity,
  instrumentIdentity,
  venueIdentity,
  dateLabel,
  errorMessage,
} from './shared';

import { ExperimentResults } from './experiment-results';
import { ErrorPanel, StatusBadge } from './load-status';

function confirmationFacts(data: Json) {
  const identity = object(data.identity);
  const analytical = object(identity.analytical);
  const period = object(identity.tradingPeriod);
  const resolution = text(analytical.resolution, '15m');
  const component = text(analytical.priceComponent, 'MID');
  const instrument = object(identity.instrument);
  const provider = object(identity.provider);
  return {
    label: text(
      data.label,
      `Experiment · ${text(data.tradingStart).slice(0, 10)} → ${text(data.tradingEnd).slice(0, 10)}`,
    ),
    status: text(data.status),
    strategy: strategyIdentity(data),
    instrument: text(instrument.code, instrumentIdentity(data)),
    provider: text(provider.name, venueIdentity(data)),
    analysis: `native ${resolution === '15m' ? 'M15' : resolution} ${component}`,
    tradingPeriod: {
      start: text(data.tradingStart ?? period.start),
      end: text(data.tradingEnd ?? period.end),
    },
  };
}

export function ExperimentStatusPage() {
  const { timeZone } = useDisplayTimeZone();
  const params = useParams<{ experimentId: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const id = params.experimentId;
  const instruction = search.get('start') === '1';
  const started = useRef(false);
  const [data, setData] = useState<Json | null>(null);
  const [error, setError] = useState('');
  const [commandError, setCommandError] = useState('');
  const [loading, setLoading] = useState(true);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePhrase, setDeletePhrase] = useState('');
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown>(null);
  const deleteInFlight = useRef(false);
  const deleteTriggerRef = useRef<HTMLButtonElement>(null);
  const deleteDialogRef = useRef<HTMLDivElement>(null);
  const deletePageRef = useRef<HTMLDivElement>(null);
  const restoreDeleteFocus = useRef(false);
  const runningSince = useRef<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const closeDeleteDialog = useCallback(() => {
    if (deletePending) return;
    restoreDeleteFocus.current = true;
    setDeleteOpen(false);
  }, [deletePending]);
  const load = useCallback(async () => {
    try {
      const value = object(await atlasApi.getExperiment(id));
      setData(value);
      if (value.status === 'RUNNING' && runningSince.current === null)
        runningSince.current = Date.now();
      if (value.status !== 'RUNNING') runningSince.current = null;
      setError('');
      return statusOf(value.status);
    } catch (reason) {
      setError(errorMessage(reason));
      return null;
    } finally {
      setLoading(false);
    }
  }, [id]);
  const run = useCallback(async () => {
    setCommandError('');
    try {
      await atlasApi.runExperiment(id);
      await load();
    } catch (reason) {
      setCommandError(
        reason instanceof ApiTransportTimeoutError
          ? 'The command timed out. Atlas may still be running it; status polling will confirm the durable outcome.'
          : errorMessage(reason),
      );
      await load();
    }
  }, [id, load]);
  const submitDelete = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      deleteInFlight.current ||
      deletePhrase !== 'DELETE' ||
      !data ||
      statusOf(data.status) === 'RUNNING'
    )
      return;
    deleteInFlight.current = true;
    setDeletePending(true);
    setDeleteError(null);
    try {
      await atlasApi.deleteExperiment(id, {
        confirmation: 'DELETE',
        expected: confirmationFacts(data),
      });
      router.push('/experiments');
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'NOT_FOUND') {
        setDeleteError('This Experiment no longer exists.');
        setDeleteOpen(false);
        router.push('/experiments');
      } else if (
        reason instanceof ApiError &&
        (reason.code === 'EXPERIMENT_RUNNING' ||
          reason.code === 'DELETE_CONFIRMATION_MISMATCH')
      ) {
        setDeleteError(reason);
        restoreDeleteFocus.current = true;
        setDeleteOpen(false);
        setDeletePhrase('');
        await load();
      } else {
        // Transport timeouts and server failures are unknown outcomes. Keep the
        // confirmation context open and never retry the destructive request.
        setDeleteError(reason);
      }
    } finally {
      deleteInFlight.current = false;
      setDeletePending(false);
    }
  };
  useEffect(() => {
    const page = deletePageRef.current;
    if (!page) return;
    if (deleteOpen) page.setAttribute('inert', '');
    else page.removeAttribute('inert');
  }, [deleteOpen]);
  useEffect(() => {
    if (deleteOpen || !restoreDeleteFocus.current) return;
    restoreDeleteFocus.current = false;
    deleteTriggerRef.current?.focus();
  }, [deleteOpen]);
  useEffect(() => {
    if (!deleteOpen) return;
    const dialog = deleteDialogRef.current;
    if (!dialog) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const focusableSelector =
      'button:not([disabled]), input:not([disabled]), [href], select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const focusable = () =>
      Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector));
    const focusFirst = () => focusable()[0]?.focus();
    focusFirst();
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const elements = focusable();
      if (elements.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    const handleFocusIn = (event: FocusEvent) => {
      if (!dialog.contains(event.target as Node)) {
        event.preventDefault();
        focusFirst();
      }
    };
    dialog.addEventListener('keydown', handleKeyDown);
    document.addEventListener('focusin', handleFocusIn);
    return () => {
      dialog.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('focusin', handleFocusIn);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [closeDeleteDialog, deleteOpen]);
  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void load().then((status) => {
        if (active && instruction && status && !started.current) {
          started.current = true;
          void run();
        }
      });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [load, run, instruction]);
  useEffect(() => {
    if (!data || (data.status !== 'PENDING' && data.status !== 'RUNNING'))
      return;
    const timer = window.setInterval(() => {
      void load();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [data, load]);
  useEffect(() => {
    if (statusOf(data?.status) !== 'RUNNING' || runningSince.current === null)
      return;
    const update = () =>
      setElapsedSeconds(
        Math.max(0, Math.floor((Date.now() - runningSince.current!) / 1000)),
      );
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [data?.status]);
  const elapsedLabel = `${Math.floor(elapsedSeconds / 60)}m ${String(elapsedSeconds % 60).padStart(2, '0')}s`;
  if (loading)
    return (
      <AppShell>
        <p className="text-sm text-atlas-foreground-muted">
          <LoaderCircle
            className="mr-2 inline size-4 animate-spin"
            aria-hidden
          />
          Loading Experiment…
        </p>
      </AppShell>
    );
  if (error && !data)
    return (
      <AppShell>
        <ErrorPanel message={error} retry={() => void load()} />
      </AppShell>
    );
  const status = statusOf(data?.status);
  const failure = object(data?.failure);
  const facts = data ? confirmationFacts(data) : null;
  return (
    <AppShell>
      <div
        ref={deletePageRef}
        data-delete-page-content
        aria-hidden={deleteOpen}
        inert={deleteOpen}
      >
        <section className="mx-auto w-full max-w-5xl space-y-8">
          <header>
            <Link
              href="/experiments"
              className="mb-5 inline-flex items-center gap-2 text-sm text-atlas-foreground-muted hover:text-atlas-foreground"
            >
              <ArrowLeft className="size-4" aria-hidden />
              Experiments
            </Link>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm text-atlas-foreground-muted">
                  Experiment · {dateLabel(data?.createdAt, timeZone)}
                </p>
                <h1 className="mt-1 text-3xl font-semibold tracking-tight">
                  {strategyIdentity(data)}
                </h1>
                <p className="mt-2 text-sm text-atlas-foreground-muted">
                  {marketIdentity(data) ? `${marketIdentity(data)} · ` : ''}
                  {facts?.analysis} · {dateLabel(data?.tradingStart, timeZone)}{' '}
                  to {dateLabel(data?.tradingEnd, timeZone)}
                </p>
              </div>
              <div className="flex flex-col items-end gap-3">
                <StatusBadge status={status} />
                {status === 'RUNNING' ? (
                  <p className="text-xs text-atlas-foreground-muted">
                    Running Experiments cannot be deleted.
                  </p>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={(event) => {
                      deleteTriggerRef.current = event.currentTarget;
                      setDeleteError(null);
                      setDeletePhrase('');
                      setDeleteOpen(true);
                    }}
                  >
                    Delete Experiment
                  </Button>
                )}
              </div>
            </div>
          </header>
          {!deleteOpen && deleteError !== null && (
            <ErrorPanel
              error={deleteError}
              message={
                typeof deleteError === 'string'
                  ? deleteError
                  : 'Deletion was not confirmed. No deletion was claimed.'
              }
            />
          )}
          {commandError && status === 'PENDING' && (
            <ErrorPanel message={commandError} retry={() => void run()} />
          )}
          {error && (
            <ErrorPanel
              message={`Status is temporarily unavailable. The Experiment state has not been changed. ${error}`}
              retry={() => void load()}
            />
          )}
          {status !== 'COMPLETED' && (
            <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
              <h2 className="font-medium">Run status</h2>
              {status === 'PENDING' && (
                <>
                  <p className="mt-2 text-sm text-atlas-foreground-muted">
                    Configuration is saved. Start the Experiment when ready.
                  </p>
                  <Button className="mt-4" onClick={() => void run()}>
                    <RefreshCw className="mr-2 size-4" aria-hidden />
                    Run Experiment
                  </Button>
                </>
              )}
              {status === 'RUNNING' && (
                <div
                  className="mt-4 flex flex-col gap-4"
                  role="status"
                  aria-live="polite"
                >
                  <div className="flex items-center gap-3 text-sm">
                    <span className="inline-flex size-2 animate-pulse rounded-full bg-atlas-positive" />
                    <span>Running deterministic simulation</span>
                    <span className="text-atlas-foreground-muted">
                      {elapsedLabel}
                    </span>
                  </div>
                  <div className="h-1 overflow-hidden rounded-full bg-atlas-surface-selected">
                    <div className="atlas-progress-indeterminate h-full w-1/3 rounded-full bg-atlas-primary" />
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-atlas-foreground-muted">
                    <span>
                      Atlas is working through the selected historical period.
                    </span>
                    <span>Last checked just now · updates every 2s</span>
                  </div>
                </div>
              )}
              {status === 'FAILED' && (
                <div className="mt-3 rounded-md border border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative">
                  <p className="font-medium">
                    No trustworthy full result was created.
                  </p>
                  <p className="mt-1">
                    {text(
                      failure.detail,
                      'The Experiment failed before a complete result was available.',
                    )}
                  </p>
                  <p className="mt-3 text-atlas-negative">
                    Review the configuration or data, then create a new
                    Experiment.
                  </p>
                </div>
              )}
            </div>
          )}
          {status === 'COMPLETED' && (
            <ExperimentResults id={id} data={data ?? {}} />
          )}
          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="border-t border-atlas-border pt-3">
              <dt className="text-xs font-medium text-atlas-foreground-muted">
                StrategyVersion
              </dt>
              <dd className="mt-1 text-sm">{strategyIdentity(data)}</dd>
            </div>
            <div className="border-t border-atlas-border pt-3">
              <dt className="text-xs font-medium text-atlas-foreground-muted">
                DatasetSnapshot
              </dt>
              <dd className="mt-1 text-sm">Immutable DatasetSnapshot</dd>
            </div>
            <div className="border-t border-atlas-border pt-3">
              <dt className="text-xs font-medium text-atlas-foreground-muted">
                Starting capital
              </dt>
              <dd className="mt-1 text-sm tabular-nums">
                {formatCurrency(data?.startingCapital)}
              </dd>
            </div>
            <div className="border-t border-atlas-border pt-3">
              <dt className="text-xs font-medium text-atlas-foreground-muted">
                Risk per Trade
              </dt>
              <dd className="mt-1 text-sm tabular-nums">
                {formatPercent(data?.riskPerTrade)}
              </dd>
            </div>
          </dl>
        </section>
      </div>
      {deleteOpen && facts && (
        <div
          className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 p-4 overscroll-contain"
          data-delete-overlay
        >
          <div
            ref={deleteDialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-experiment-title"
            aria-describedby="delete-experiment-description"
            tabIndex={-1}
            onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
              if (event.key === 'Escape') {
                event.preventDefault();
                closeDeleteDialog();
              }
            }}
            className="max-h-[calc(100vh-2rem)] w-[min(42rem,calc(100%-2rem))] overflow-y-auto rounded-lg border border-atlas-border bg-atlas-surface p-0 text-atlas-foreground shadow-xl"
          >
            <form onSubmit={submitDelete} className="flex flex-col gap-5 p-6">
              <div>
                <h2
                  id="delete-experiment-title"
                  className="text-xl font-semibold"
                >
                  Delete Experiment permanently?
                </h2>
                <p
                  id="delete-experiment-description"
                  className="mt-2 text-sm text-atlas-foreground-muted"
                >
                  This cannot be undone. Experiment-owned results, decisions,
                  orders, fills, trades, and equity will be removed.
                </p>
              </div>
              <dl className="grid gap-3 rounded-md border border-atlas-border bg-atlas-surface-hover p-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-atlas-foreground-muted">
                    Experiment
                  </dt>
                  <dd>{facts.label}</dd>
                </div>
                <div>
                  <dt className="text-xs text-atlas-foreground-muted">
                    Current status
                  </dt>
                  <dd>{facts.status}</dd>
                </div>
                <div>
                  <dt className="text-xs text-atlas-foreground-muted">
                    StrategyVersion
                  </dt>
                  <dd>{facts.strategy}</dd>
                </div>
                <div>
                  <dt className="text-xs text-atlas-foreground-muted">
                    Market
                  </dt>
                  <dd>
                    {facts.instrument} · {facts.provider}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-atlas-foreground-muted">
                    Analysis
                  </dt>
                  <dd>{facts.analysis}</dd>
                </div>
                <div>
                  <dt className="text-xs text-atlas-foreground-muted">
                    Trading period (UTC)
                  </dt>
                  <dd>
                    {facts.tradingPeriod.start} → {facts.tradingPeriod.end}
                  </dd>
                </div>
              </dl>
              <p className="text-sm text-atlas-foreground-muted">
                Shared DatasetSnapshot data, canonical bars, and acquisition
                history are retained.
              </p>
              {deleteError !== null && (
                <ErrorPanel
                  error={deleteError}
                  message={
                    typeof deleteError === 'string'
                      ? deleteError
                      : 'Deletion was not confirmed. No deletion was claimed.'
                  }
                />
              )}
              <label
                htmlFor="delete-confirmation"
                className="flex flex-col gap-2 text-sm font-medium"
              >
                Type <span className="font-mono">DELETE</span> to confirm
                <input
                  id="delete-confirmation"
                  name="delete-confirmation"
                  value={deletePhrase}
                  onChange={(event) => setDeletePhrase(event.target.value)}
                  disabled={deletePending}
                  autoComplete="off"
                  className="min-h-10 rounded-md border border-atlas-control-border bg-atlas-background px-3 font-normal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-focus-ring"
                />
              </label>
              <div className="flex justify-end gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={deletePending}
                  onClick={closeDeleteDialog}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={deletePending || deletePhrase !== 'DELETE'}
                  className="border border-atlas-negative text-atlas-negative disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {deletePending ? 'Deleting…' : 'Delete permanently'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
