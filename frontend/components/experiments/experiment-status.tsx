'use client';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import type { FormEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import type React from 'react';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { AppShell } from '../app-shell';
import { Button } from '../ui/button';
import { Select } from '../ui/select';
import { UtcDateTimePicker } from '../utc-date-time-picker';
import {
  ApiError,
  ApiTransportTimeoutError,
  ApiUnavailableError,
  atlasApi,
} from '../../lib/api-client';
import {
  formatChartTime,
  formatChartTick,
  formatInstant,
  parseUtcInput,
  utcInputFromInstant,
} from '../../lib/time';
import { useDisplayTimeZone } from '../../app/providers';
import { chartRoles, strictlyAscending } from './chart-support';
import {
  formatCurrency,
  formatMoney,
  formatPercent,
  formatPrice,
  formatRatio,
} from '../../lib/experiment-formatters';
import type { Json } from './shared';
import {
  object,
  text,
  strategyIdentity,
  statusOf,
  marketIdentity,
  dateLabel,
  errorMessage,
  productNextAction,
  scalarFields,
  parameterDefaults,
  snapshotLabel,
  diagnosticLabel,
  formattedMetric,
  metricState,
  priceLabel,
  moneyLabel,
  rLabel,
  percentLabel,
} from './shared';

import { ExperimentResults } from './experiment-results';
import { ErrorPanel, StatusBadge } from './load-status';

export function ExperimentStatusPage() {
  const { timeZone } = useDisplayTimeZone();
  const params = useParams<{ experimentId: string }>();
  const search = useSearchParams();
  const id = params.experimentId;
  const instruction = search.get('start') === '1';
  const started = useRef(false);
  const [data, setData] = useState<Json | null>(null);
  const [error, setError] = useState('');
  const [commandError, setCommandError] = useState('');
  const [loading, setLoading] = useState(true);
  const runningSince = useRef<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
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
  return (
    <AppShell>
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
                {dateLabel(data?.tradingStart, timeZone)} to{' '}
                {dateLabel(data?.tradingEnd, timeZone)}
              </p>
            </div>
            <StatusBadge status={status} />
          </div>
        </header>
        {commandError && status === 'PENDING' && (
          <ErrorPanel message={commandError} retry={() => void run()} />
        )}
        {error && (
          <ErrorPanel
            message={`Status is temporarily unavailable. The Experiment state has not been changed. ${error}`}
            retry={() => void load()}
          />
        )}
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
            <div className="mt-4 space-y-4" role="status" aria-live="polite">
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
                Review the configuration or data, then create a new Experiment.
              </p>
            </div>
          )}
          {status === 'COMPLETED' && (
            <div className="mt-6">
              <ExperimentResults id={id} data={data ?? {}} />
            </div>
          )}
        </div>
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
    </AppShell>
  );
}
