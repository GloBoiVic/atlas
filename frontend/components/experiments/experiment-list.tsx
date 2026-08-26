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
import { ErrorPanel } from './load-status';
import { StatusBadge } from './load-status';

export function ExperimentsList() {
  const { timeZone } = useDisplayTimeZone();
  const [items, setItems] = useState<unknown[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const load = useCallback(() => {
    setState('loading');
    atlasApi
      .listExperiments({ limit: 50 })
      .then((value) => {
        const nextItems = object(value).items;
        setItems(Array.isArray(nextItems) ? nextItems : []);
        setState('ready');
      })
      .catch((reason) => {
        setError(errorMessage(reason));
        setState('error');
      });
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  return (
    <AppShell>
      <section aria-labelledby="experiments-heading" className="space-y-8">
        <header className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="mb-2 text-sm font-medium text-atlas-primary">
              Historical simulation workspace
            </p>
            <h1
              id="experiments-heading"
              className="text-3xl font-semibold tracking-tight"
            >
              Experiments
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
              Configure a deterministic historical simulation, validate its
              data, and observe the durable run state.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/experiments/new"
              className="inline-flex min-h-10 items-center rounded-md bg-atlas-primary px-4 text-sm font-medium text-atlas-primary-foreground hover:bg-atlas-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-focus-ring focus-visible:ring-offset-2"
            >
              Run Experiment
            </Link>
            <Link
              aria-disabled={selected.length < 2 || selected.length > 4}
              tabIndex={
                selected.length < 2 || selected.length > 4 ? -1 : undefined
              }
              href={
                selected.length >= 2 && selected.length <= 4
                  ? `/experiments/compare?${selected.map((id) => `experimentId=${encodeURIComponent(id)}`).join('&')}`
                  : '/experiments'
              }
              className={`inline-flex min-h-10 items-center rounded-md border px-4 text-sm font-medium ${selected.length >= 2 && selected.length <= 4 ? 'border-atlas-control-border bg-atlas-surface text-atlas-foreground hover:bg-atlas-surface-hover' : 'cursor-not-allowed border-atlas-border text-atlas-foreground-disabled'}`}
            >
              Compare selected{' '}
              <span className="ml-1 text-xs">({selected.length}/4)</span>
            </Link>
          </div>
        </header>
        {state === 'error' && <ErrorPanel message={error} retry={load} />}
        {state === 'loading' && (
          <div className="rounded-lg border border-atlas-border bg-atlas-surface p-8 text-sm text-atlas-foreground-muted">
            <LoaderCircle
              className="mr-2 inline size-4 animate-spin"
              aria-hidden
            />
            Loading Experiments…
          </div>
        )}
        {state === 'ready' && items.length === 0 && (
          <div className="rounded-lg border border-dashed border-atlas-control-border bg-atlas-surface px-6 py-12 text-center">
            <h2 className="text-lg font-medium">No Experiments yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-atlas-foreground-muted">
              Start with a validated historical simulation using an existing
              StrategyVersion and DatasetSnapshot.
            </p>
            <Link
              href="/experiments/new"
              className="mt-5 inline-flex text-sm font-medium text-atlas-primary underline underline-offset-4"
            >
              Run your first Experiment
            </Link>
          </div>
        )}
        {state === 'ready' && items.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-atlas-border bg-atlas-surface">
            <table className="w-full min-w-[900px] text-left text-sm">
              <caption className="sr-only">Experiments, newest first</caption>
              <thead className="border-b border-atlas-border bg-atlas-surface-hover text-xs font-medium text-atlas-foreground-muted">
                <tr>
                  {[
                    'Select',
                    'Experiment',
                    'StrategyVersion',
                    'Period',
                    'Status',
                    'Net Return',
                    'Max Drawdown',
                    'Sharpe',
                    'Trades',
                    'Created',
                  ].map((heading) => (
                    <th key={heading} className="px-4 py-3">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-atlas-border">
                {items.map((raw, index) => {
                  const item = object(raw);
                  const status = statusOf(item.status);
                  return (
                    <tr
                      key={text(item.id, String(index))}
                      className="hover:bg-atlas-surface-hover"
                    >
                      <td className="px-4 py-4">
                        {status === 'COMPLETED' ? (
                          <input
                            aria-label={`Select Experiment ${index + 1}`}
                            type="checkbox"
                            checked={selected.includes(text(item.id))}
                            onChange={() =>
                              setSelected((current) =>
                                current.includes(text(item.id))
                                  ? current.filter((id) => id !== text(item.id))
                                  : current.length < 4
                                    ? [...current, text(item.id)]
                                    : current,
                              )
                            }
                            className="size-4 accent-atlas-primary"
                          />
                        ) : (
                          <span
                            className="text-xs text-atlas-foreground-disabled"
                            title="Only COMPLETED Experiments can be compared"
                          >
                            Not eligible
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <Link
                          className="font-medium text-atlas-foreground underline-offset-4 hover:underline"
                          href={`/experiments/${text(item.id)}`}
                        >
                          Experiment {index + 1}
                        </Link>
                      </td>
                      <td className="px-4 py-4 text-atlas-foreground-muted">
                        {strategyIdentity(item)}
                      </td>
                      <td className="px-4 py-4 text-atlas-foreground-muted">
                        {dateLabel(item.tradingStart, timeZone)}
                        <span className="block text-xs text-atlas-foreground-disabled">
                          to {dateLabel(item.tradingEnd, timeZone)}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <StatusBadge status={status} />
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? formattedMetric(
                              object(item.metrics).netReturn,
                              'percent',
                            )
                          : '—'}
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? formattedMetric(
                              object(item.metrics).maxDrawdownPercent,
                              'percent',
                            )
                          : '—'}
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? formattedMetric(object(item.metrics).sharpe, 'r')
                          : '—'}
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? formattedMetric(object(item.metrics).tradeCount)
                          : '—'}
                      </td>
                      <td className="px-4 py-4 text-atlas-foreground-muted">
                        {dateLabel(item.createdAt, timeZone)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}
