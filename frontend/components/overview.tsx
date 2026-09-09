'use client';

import Link from 'next/link';
import { useCallback } from 'react';
import { AlertCircle } from 'lucide-react';
import { atlasApi } from '../lib/api-client';
import { useDisplayTimeZone } from '../app/providers';
import { EmptyState, LoadingState, useReadResource } from './read-resource';
import { PaperActiveStatusSection } from './paper-status';
import { PaperBrokerStateSection } from './paper-broker-state';
import {
  experimentHeadlineMetrics,
  experimentIdentity,
  experimentPeriod,
  object,
  statusLabel,
  strategyIdentity,
  text,
} from './experiments/shared';

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

function OverviewReadError({
  error,
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  const message =
    error instanceof Error
      ? error.message
      : 'Atlas could not complete this read request.';

  return (
    <div
      role="alert"
      className="flex items-start gap-3 border-l-2 border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
    >
      <AlertCircle aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div>
        <p>{message}</p>
        <button
          type="button"
          onClick={retry}
          className="mt-3 font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-focus-ring focus-visible:ring-offset-2"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

function healthLabel(value: unknown) {
  switch (String(value).toLowerCase()) {
    case 'ready':
    case 'ok':
      return 'Ready';
    case 'not_ready':
      return 'Not ready';
    case 'unavailable':
      return 'Unavailable';
    default:
      return display(value);
  }
}

function SystemSection() {
  const loader = useCallback(() => atlasApi.ready(), []);
  const { state, retry } = useReadResource<Health>(loader);
  const healthy =
    state.status === 'ready' &&
    state.data.status === 'ready' &&
    state.data.checks.database === 'ok';

  return (
    <section aria-labelledby="system-heading" className="space-y-4">
      <div>
        <h2 id="system-heading" className="text-lg font-semibold">
          System
        </h2>
      </div>
      {state.status === 'loading' && <LoadingState label="system readiness" />}
      {state.status === 'error' && (
        <OverviewReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && (
        <div className="space-y-4">
          <p
            role="status"
            className={
              healthy
                ? 'status status-success'
                : 'status rounded border border-atlas-warning bg-atlas-warning-muted px-2.5 py-1 text-atlas-warning'
            }
          >
            {healthy ? 'Ready' : 'Needs attention'}
          </p>
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <Fact label="API" value={healthLabel(state.data.status)} />
            <Fact
              label="Database"
              value={healthLabel(state.data.checks.database)}
            />
          </dl>
        </div>
      )}
    </section>
  );
}

function StrategySection() {
  const loader = useCallback(() => atlasApi.listStrategies(), []);
  const { state, retry } = useReadResource<Strategies>(loader);

  return (
    <section aria-labelledby="strategies-summary-heading" className="space-y-4">
      <div>
        <h2 id="strategies-summary-heading" className="text-lg font-semibold">
          Strategies
        </h2>
      </div>
      {state.status === 'loading' && <LoadingState label="Strategies" />}
      {state.status === 'error' && (
        <OverviewReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && state.data.items.length === 0 && (
        <EmptyState>No Strategies</EmptyState>
      )}
      {state.status === 'ready' && state.data.items.length > 0 && (
        <ul className="divide-y divide-atlas-border border-y border-atlas-border">
          {state.data.items.slice(0, 3).map((item) => (
            <li key={item.strategyKey} className="py-3 first:pt-0 last:pb-0">
              <Link
                href={`/strategies/${encodeURIComponent(item.strategyKey)}`}
                className="font-medium text-atlas-primary underline-offset-4 hover:underline"
              >
                {item.name}
              </Link>
              <p className="mt-1 text-sm text-atlas-foreground-muted">
                {item.latestVersion?.displayName ??
                  'Latest version unavailable'}
              </p>
              {typeof item.experimentCount === 'number' && (
                <p className="mt-1 text-xs text-atlas-foreground-muted">
                  {item.experimentCount} Experiments
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      <Link
        href="/strategies"
        className="inline-flex text-sm font-medium text-atlas-primary underline-offset-4 hover:underline"
      >
        View Strategies
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
      ? state.data.items.slice(0, 3)
      : [];
  const { timeZone } = useDisplayTimeZone();

  return (
    <section aria-labelledby="experiment-summary-heading" className="space-y-4">
      <div>
        <h2 id="experiment-summary-heading" className="text-lg font-semibold">
          Experiments
        </h2>
      </div>
      {state.status === 'loading' && <LoadingState label="Experiments" />}
      {state.status === 'error' && (
        <OverviewReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && items.length === 0 && (
        <EmptyState>No Experiments</EmptyState>
      )}
      {state.status === 'ready' && items.length > 0 && (
        <ul className="divide-y divide-atlas-border border-y border-atlas-border">
          {items.map((raw, index) => {
            const item = object(raw);
            const id = text(item.id, '');
            const status = statusLabel(item.status);
            const identity = experimentIdentity(item);
            const metrics = experimentHeadlineMetrics(item);
            const metricParts =
              status === 'COMPLETED'
                ? [
                    metrics.netReturn !== '—' ? metrics.netReturn : null,
                    metrics.trades !== '—'
                      ? `${metrics.trades} ${metrics.trades === '1' ? 'trade' : 'trades'}`
                      : null,
                  ].filter((value): value is string => value !== null)
                : [];
            const period = experimentPeriod(item, timeZone);

            return (
              <li
                key={id || `${identity}-${index}`}
                className="space-y-1 py-3 first:pt-0 last:pb-0"
              >
                {id ? (
                  <Link
                    href={`/experiments/${encodeURIComponent(id)}`}
                    className="font-medium text-atlas-foreground underline-offset-4 hover:underline"
                  >
                    {identity}
                  </Link>
                ) : (
                  <span className="font-medium">{identity}</span>
                )}
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-atlas-foreground-muted">
                  <span className="status status-muted">{status}</span>
                  <span>{strategyIdentity(item)}</span>
                </div>
                {metricParts.length > 0 && (
                  <p className="text-sm tabular-nums text-atlas-foreground-muted">
                    {metricParts.join(' · ')}
                  </p>
                )}
                {period !== 'Period unavailable' && (
                  <p className="text-xs text-atlas-foreground-muted">
                    {period}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex flex-wrap gap-3">
        <Link href="/experiments" className="action-secondary">
          View Experiments
        </Link>
        <Link href="/experiments/new" className="action-primary">
          Run Experiment
        </Link>
      </div>
    </section>
  );
}

export function Overview() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
      <header className="max-w-3xl">
        <h1
          id="overview-heading"
          className="text-3xl font-semibold tracking-tight"
        >
          Overview
        </h1>
      </header>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5 lg:col-span-3">
          <PaperBrokerStateSection compact />
          <div className="mt-6 border-t border-atlas-border pt-6">
            <PaperActiveStatusSection compact />
          </div>
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <StrategySection />
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <ExperimentSection />
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <SystemSection />
        </div>
      </div>
    </div>
  );
}
