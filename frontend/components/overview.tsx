'use client';

import Link from 'next/link';
import { useCallback } from 'react';
import { atlasApi } from '../lib/api-client';
import {
  EmptyState,
  LoadingState,
  ReadError,
  UnavailableState,
  useReadResource,
} from './read-resource';
import {
  PaperActiveStatusSection,
  PaperCapabilitySection,
} from './paper-status';
import {
  HistoricalCapabilitySection,
  SnapshotOptionsSection,
} from './data-overview';

type Health = Awaited<ReturnType<typeof atlasApi.ready>>;
type Strategies = Awaited<ReturnType<typeof atlasApi.listStrategies>>;

function display(value: unknown) {
  return value === null || value === undefined || value === ''
    ? '—'
    : String(value);
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-atlas-border pt-3">
      <dt className="text-xs text-atlas-foreground-muted">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{value}</dd>
    </div>
  );
}

function ReadinessSection() {
  const loader = useCallback(() => atlasApi.ready(), []);
  const { state, retry } = useReadResource<Health>(loader);

  return (
    <section aria-labelledby="readiness-heading" className="space-y-4">
      <div>
        <h2 id="readiness-heading" className="text-lg font-semibold">
          API and database readiness
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Readiness is a system check, not a PAPER connectivity claim.
        </p>
      </div>
      {state.status === 'loading' && <LoadingState label="system readiness" />}
      {state.status === 'error' && (
        <ReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && (
        <div className="space-y-4">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <Fact label="API" value={display(state.data.status)} />
            <Fact
              label="Database"
              value={display(state.data.checks.database)}
            />
          </dl>
          {(state.data.status !== 'ready' ||
            state.data.checks.database !== 'ok') && (
            <UnavailableState>
              Readiness is unavailable. The API reports{' '}
              {display(state.data.status)} and the database check reports{' '}
              {display(state.data.checks.database)}.
            </UnavailableState>
          )}
        </div>
      )}
    </section>
  );
}

function StrategySection() {
  const loader = useCallback(() => atlasApi.listStrategies(), []);
  const { state, retry } = useReadResource<Strategies>(loader);

  return (
    <section aria-labelledby="strategy-summary-heading" className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 id="strategy-summary-heading" className="text-lg font-semibold">
            Strategy catalog
          </h2>
          <p className="mt-1 text-sm text-atlas-foreground-muted">
            Count of items returned by the catalog read.
          </p>
        </div>
        {state.status === 'ready' && (
          <span className="text-sm tabular-nums text-atlas-foreground-muted">
            {state.data.items.length} returned items
          </span>
        )}
      </div>
      {state.status === 'loading' && <LoadingState label="Strategy catalog" />}
      {state.status === 'error' && (
        <ReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && state.data.items.length === 0 && (
        <EmptyState>No Strategy catalog items were returned.</EmptyState>
      )}
      <Link
        href="/strategies"
        className="inline-flex text-sm font-medium text-atlas-primary underline-offset-4 hover:underline"
      >
        Open Strategies
      </Link>
    </section>
  );
}

type ExperimentList = { items?: unknown[] };

function ExperimentSection() {
  const loader = useCallback(
    () => atlasApi.listExperiments({ limit: 8 }) as Promise<ExperimentList>,
    [],
  );
  const { state, retry } = useReadResource<ExperimentList>(loader);
  const items =
    state.status === 'ready' && Array.isArray(state.data.items)
      ? state.data.items
      : [];

  const counts = new Map<string, number>();
  for (const item of items) {
    const status =
      item && typeof item === 'object' && 'status' in item
        ? (item as { status?: unknown }).status
        : undefined;
    if (typeof status === 'string' && status.length > 0) {
      counts.set(status, (counts.get(status) ?? 0) + 1);
    }
  }

  return (
    <section aria-labelledby="experiment-summary-heading" className="space-y-4">
      <div>
        <h2 id="experiment-summary-heading" className="text-lg font-semibold">
          Experiments
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Status summary for the visible first page only; no global total or
          performance metric is inferred.
        </p>
      </div>
      {state.status === 'loading' && (
        <LoadingState label="visible Experiments" />
      )}
      {state.status === 'error' && (
        <ReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && items.length === 0 && (
        <EmptyState>
          No Experiment items were returned on the first page.
        </EmptyState>
      )}
      {state.status === 'ready' && items.length > 0 && (
        <div className="space-y-2 text-sm">
          <p className="text-atlas-foreground-muted">
            {items.length} returned items on the visible first page.
          </p>
          {counts.size > 0 ? (
            <ul className="flex flex-wrap gap-x-5 gap-y-2">
              {Array.from(counts, ([status, count]) => (
                <li key={status}>
                  <span className="font-mono text-atlas-primary">{status}</span>{' '}
                  <span className="text-atlas-foreground-muted">
                    {count} returned
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-atlas-foreground-muted">
              No status values were included in the returned items.
            </p>
          )}
        </div>
      )}
      <Link
        href="/experiments"
        className="inline-flex text-sm font-medium text-atlas-primary underline-offset-4 hover:underline"
      >
        Open Experiments
      </Link>
    </section>
  );
}

export function Overview() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
      <header className="max-w-3xl">
        <p className="mb-2 text-sm font-medium text-atlas-primary">
          Trader workspace
        </p>
        <h1
          id="overview-heading"
          className="text-3xl font-semibold tracking-tight"
        >
          Overview
        </h1>
        <p className="mt-3 text-sm leading-6 text-atlas-foreground-muted">
          Atlas is where the trader creates methodologies, runs deterministic
          historical experiments, and operates approved methodology through
          PAPER.
        </p>
      </header>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <ReadinessSection />
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <StrategySection />
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <ExperimentSection />
        </div>
        <div className="space-y-6 rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <PaperCapabilitySection compact />
          <PaperActiveStatusSection compact />
        </div>
        <div className="space-y-6 rounded-lg border border-atlas-border bg-atlas-surface p-5 lg:col-span-2">
          <HistoricalCapabilitySection compact />
          <div className="border-t border-atlas-border pt-6">
            <SnapshotOptionsSection compact />
          </div>
        </div>
      </div>
      <section
        aria-labelledby="next-steps-heading"
        className="border-t border-atlas-border pt-6"
      >
        <h2 id="next-steps-heading" className="text-lg font-semibold">
          Next steps
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Continue through the read-only lifecycle surfaces and existing
          research workflows.
        </p>
        <nav
          aria-label="Overview next steps"
          className="mt-4 flex flex-wrap gap-3"
        >
          <Link href="/strategies" className="action-secondary">
            Review Strategies
          </Link>
          <Link href="/experiments/new" className="action-primary">
            Configure an Experiment
          </Link>
          <Link href="/experiments" className="action-secondary">
            Inspect Experiments
          </Link>
          <Link href="/data" className="action-secondary">
            Inspect Data
          </Link>
          <Link href="/paper" className="action-secondary">
            View PAPER status
          </Link>
        </nav>
      </section>
    </div>
  );
}
