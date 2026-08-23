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
import { AppShell } from './app-shell';
import { Button } from './ui/button';
import { ApiTransportTimeoutError, atlasApi } from '../lib/api-client';

type Json = Record<string, unknown>;
type Status = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

const object = (value: unknown): Json =>
  value && typeof value === 'object' ? (value as Json) : {};
const text = (value: unknown, fallback = '—') =>
  typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : fallback;
const statusOf = (value: unknown): Status =>
  value === 'RUNNING' || value === 'COMPLETED' || value === 'FAILED'
    ? value
    : 'PENDING';
const dateLabel = (value: unknown) => {
  if (typeof value !== 'string') return '—';
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : date.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
};
const dateInput = (value: string) => (value ? value.slice(0, 16) : '');
const iso = (value: string) => new Date(value).toISOString();
const metric = (value: unknown) => {
  const data = object(value);
  if (data.state === 'INFINITE') return '∞';
  return data.state === 'VALUE' ? text(data.value) : '—';
};
const metricState = (value: unknown) => object(value);
const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : 'Atlas could not complete that request.';

function StatusBadge({ status }: { status: Status }) {
  const labels = {
    PENDING: 'Pending',
    RUNNING: 'Running',
    COMPLETED: 'Completed',
    FAILED: 'Failed',
  };
  return (
    <span
      className={`status rounded-full border px-2.5 py-1 ${status === 'FAILED' ? 'border-red-200 bg-red-50 text-red-800' : status === 'COMPLETED' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-slate-50 text-slate-700'}`}
    >
      <span aria-hidden>●</span>
      {labels[status]}
    </span>
  );
}

function ErrorPanel({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900"
    >
      <AlertCircle aria-hidden className="mt-0.5 size-5 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">Atlas could not confirm this request</p>
        <p className="mt-1 text-red-800">{message}</p>
        {retry && (
          <button
            onClick={retry}
            className="mt-3 font-medium underline underline-offset-2"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  format = 'number',
}: {
  label: string;
  value: unknown;
  format?: 'number' | 'percent' | 'money';
}) {
  const data = metricState(value);
  const shown =
    data.state === 'VALUE'
      ? text(data.value)
      : data.state === 'INFINITE'
        ? '∞'
        : 'Unavailable';
  const formatted =
    format === 'money' && shown !== 'Unavailable' && shown !== '∞'
      ? `$${shown}`
      : format === 'percent' && shown !== 'Unavailable' && shown !== '∞'
        ? `${shown}`
        : shown;
  return (
    <div className="border-t border-slate-200 pt-3">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd
        className={`mt-1 text-lg font-semibold tabular-nums ${data.state === 'UNAVAILABLE' ? 'text-slate-500' : ''}`}
      >
        {formatted}
      </dd>
      {data.state !== 'VALUE' && data.state !== 'INFINITE' && (
        <p className="mt-1 text-xs text-slate-500">
          {text(data.reason, 'Not defined for this result')}
        </p>
      )}
    </div>
  );
}

function Chart({
  points,
  kind = 'equity',
}: {
  points: unknown[];
  kind?: 'equity' | 'drawdown';
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let chart: import('lightweight-charts').IChartApi | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({ createChart, LineSeries, ColorType }) => {
        if (!ref.current || disposed) return;
        chart = createChart(ref.current, {
          height: 260,
          layout: {
            background: { type: ColorType.Solid, color: '#ffffff' },
            textColor: '#475569',
          },
          grid: {
            vertLines: { color: '#f1f5f9' },
            horzLines: { color: '#f1f5f9' },
          },
          rightPriceScale: { borderColor: '#e2e8f0' },
          timeScale: { borderColor: '#e2e8f0' },
        });
        const series = chart.addSeries(LineSeries, {
          color: kind === 'drawdown' ? '#b45309' : '#2563eb',
          lineWidth: 2,
          priceLineVisible: false,
        });
        const data = points
          .map((raw) => {
            const item = object(raw);
            const date = new Date(text(item.observed_at, '')).getTime() / 1000;
            return {
              time: date as import('lightweight-charts').Time,
              value: Number(
                text(
                  item[kind === 'drawdown' ? 'drawdown_amount' : 'equity'],
                  '0',
                ),
              ),
            };
          })
          .filter(
            (item) => Number.isFinite(item.time) && Number.isFinite(item.value),
          );
        if (data.length)
          series.setData(data.sort((a, b) => Number(a.time) - Number(b.time)));
        chart.timeScale().fitContent();
        const observer = new ResizeObserver(() =>
          chart?.applyOptions({ width: ref.current?.clientWidth ?? 0 }),
        );
        observer.observe(ref.current);
        (
          chart as import('lightweight-charts').IChartApi & {
            __observer?: ResizeObserver;
          }
        ).__observer = observer;
      },
    );
    return () => {
      disposed = true;
      const observer = (
        chart as
          | (import('lightweight-charts').IChartApi & {
              __observer?: ResizeObserver;
            })
          | undefined
      )?.__observer;
      observer?.disconnect();
      chart?.remove();
    };
  }, [kind, points]);
  return (
    <div ref={ref} className="h-[260px] w-full" aria-label={`${kind} chart`} />
  );
}

function StateDisclosure({ data }: { data: Json }) {
  const config = object(data.simulationConfig);
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-5 text-sm">
      <h2 className="font-medium">Assumptions and provenance</h2>
      <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2">
        <div>
          <dt className="text-slate-500">StrategyVersion</dt>
          <dd className="font-medium">EMA Sweep Engulfing</dd>
        </div>
        <div>
          <dt className="text-slate-500">Instrument / account</dt>
          <dd className="font-medium">EUR/USD · OANDA Practice · PAPER</dd>
        </div>
        <div>
          <dt className="text-slate-500">Period</dt>
          <dd>
            {dateLabel(data.tradingStart)} → {dateLabel(data.tradingEnd)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Starting capital / Risk</dt>
          <dd>
            ${text(data.startingCapital)} · {text(data.riskPerTrade)} per Trade
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Execution</dt>
          <dd>
            {text(config.execution_resolution, 'M1')} · BID/ASK · MID analysis
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Financing</dt>
          <dd className="font-medium">FINANCING EXCLUDED</dd>
        </div>
        <div>
          <dt className="text-slate-500">DatasetSnapshot</dt>
          <dd>Immutable snapshot provenance retained by Atlas</dd>
        </div>
        <div>
          <dt className="text-slate-500">Model</dt>
          <dd>{text(data.modelVersion)}</dd>
        </div>
      </dl>
      <p className="mt-5 text-xs leading-5 text-slate-600">
        Spread is embedded in BID/ASK execution and is not double-counted. Chart
        sampling, if disclosed above, is presentation-only and never feeds
        metrics.
      </p>
    </div>
  );
}

function EquityResults({ id, data }: { id: string; data: Json }) {
  const [equity, setEquity] = useState<Json | null>(null);
  const [trades, setTrades] = useState<unknown[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([atlasApi.getEquity(id), atlasApi.listTrades(id)])
      .then(([series, list]) => {
        setEquity(object(series));
        const items = object(list).items;
        setTrades(Array.isArray(items) ? items : []);
      })
      .catch((reason) => setError(errorMessage(reason)));
  }, [id]);
  const points = Array.isArray(equity?.points) ? equity.points : [];
  const metrics = object(data.metrics);
  const zeroTrades = metricState(metrics.tradeCount).value === '0';
  const ambiguous = trades.filter(
    (trade) => object(trade).ambiguous === true,
  ).length;
  return (
    <div className="space-y-8">
      <section aria-labelledby="metrics-heading">
        <h2 id="metrics-heading" className="text-lg font-semibold">
          Result
        </h2>
        <dl className="mt-4 grid gap-x-6 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Net Return"
            value={metrics.netReturn}
            format="percent"
          />
          <MetricCard
            label="Max Drawdown"
            value={metrics.maxDrawdownPercent}
            format="percent"
          />
          <MetricCard label="Sharpe" value={metrics.sharpe} />
          <MetricCard label="Profit Factor" value={metrics.profitFactor} />
          <MetricCard
            label="Win Rate"
            value={metrics.winRate}
            format="percent"
          />
          <MetricCard
            label="Expectancy"
            value={metrics.expectancy}
            format="money"
          />
          <MetricCard label="Trade Count" value={metrics.tradeCount} />
        </dl>
      </section>
      {zeroTrades && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
          <strong>No Trades</strong> — Strategy produced no executed Trades
          during this period. Return, drawdown, and Trade Count remain valid;
          Trade-dependent metrics are unavailable.
        </div>
      )}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Equity curve</h2>
          <p className="text-sm text-slate-600">
            Full canonical equity history.{' '}
            {text(equity?.samplingPolicy, '') === 'EQUITY_ENVELOPE_V1'
              ? `Displayed envelope sampled from ${text(equity?.sourceCount)} points; omitted ranges are presentation-only.`
              : ''}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <Chart points={points} />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Drawdown</h2>
          <p className="text-sm text-slate-600">
            Amount below the running equity peak.
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <Chart points={points} kind="drawdown" />
        </div>
      </section>
      <section aria-labelledby="trades-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h2 id="trades-heading" className="text-lg font-semibold">
              Trades
            </h2>
            <p className="text-sm text-slate-600">
              Completed Trade episodes, ordered by sequence.
            </p>
          </div>
          {ambiguous > 0 && (
            <p className="text-sm text-amber-800">
              {ambiguous} ambiguous · Stop-first policy applied
            </p>
          )}
        </div>
        {error && (
          <ErrorPanel message={error} retry={() => window.location.reload()} />
        )}
        {trades.length ? (
          <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full min-w-[760px] text-left text-sm">
              <caption className="sr-only">Experiment Trades</caption>
              <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-600">
                <tr>
                  {[
                    'Trade',
                    'Direction',
                    'Opened',
                    'Closed',
                    'Entry',
                    'Exit',
                    'Net P&L',
                    'R',
                    'Result',
                  ].map((heading) => (
                    <th key={heading} className="px-4 py-3">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {trades.map((raw) => {
                  const trade = object(raw);
                  const seq = Number(text(trade.sequence_number, '0'));
                  return (
                    <tr key={seq}>
                      <td className="px-4 py-3">
                        <Link
                          className="font-medium text-blue-700 underline-offset-4 hover:underline"
                          href={`/experiments/${id}/trades/${seq}`}
                        >
                          Trade {seq}
                        </Link>
                      </td>
                      <td className="px-4 py-3">{text(trade.direction)}</td>
                      <td className="px-4 py-3">
                        {dateLabel(trade.opened_at)}
                      </td>
                      <td className="px-4 py-3">
                        {dateLabel(trade.closed_at)}
                      </td>
                      <td className="px-4 py-3 tabular-nums">
                        {text(trade.entry_price)}
                      </td>
                      <td className="px-4 py-3 tabular-nums">
                        {text(trade.exit_price)}
                      </td>
                      <td className="px-4 py-3 tabular-nums">
                        ${text(trade.net_pnl)}
                      </td>
                      <td className="px-4 py-3 tabular-nums">
                        {text(trade.r_multiple)}
                      </td>
                      <td className="px-4 py-3">
                        {trade.ambiguous
                          ? 'Ambiguous'
                          : text(trade.exit_reason)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-600">
            No executed Trades for this Experiment.
          </div>
        )}
      </section>
      <StateDisclosure data={data} />
    </div>
  );
}

export function ExperimentsList() {
  const [items, setItems] = useState<unknown[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [error, setError] = useState('');
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
            <p className="mb-2 text-sm font-medium text-blue-700">
              Historical simulation workspace
            </p>
            <h1
              id="experiments-heading"
              className="text-3xl font-semibold tracking-tight"
            >
              Experiments
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Configure a deterministic historical simulation, validate its
              data, and observe the durable run state.
            </p>
          </div>
          <Link
            href="/experiments/new"
            className="inline-flex min-h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
          >
            Run Experiment
          </Link>
        </header>
        {state === 'error' && <ErrorPanel message={error} retry={load} />}
        {state === 'loading' && (
          <div className="rounded-lg border border-slate-200 bg-white p-8 text-sm text-slate-600">
            <LoaderCircle
              className="mr-2 inline size-4 animate-spin"
              aria-hidden
            />
            Loading Experiments…
          </div>
        )}
        {state === 'ready' && items.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
            <h2 className="text-lg font-medium">No Experiments yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">
              Start with a validated EUR/USD historical simulation using an
              existing StrategyVersion and DatasetSnapshot.
            </p>
            <Link
              href="/experiments/new"
              className="mt-5 inline-flex text-sm font-medium text-blue-700 underline underline-offset-4"
            >
              Run your first Experiment
            </Link>
          </div>
        )}
        {state === 'ready' && items.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full min-w-[900px] text-left text-sm">
              <caption className="sr-only">Experiments, newest first</caption>
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                <tr>
                  {[
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
              <tbody className="divide-y divide-slate-100">
                {items.map((raw, index) => {
                  const item = object(raw);
                  const status = statusOf(item.status);
                  return (
                    <tr
                      key={text(item.id, String(index))}
                      className="hover:bg-slate-50"
                    >
                      <td className="px-4 py-4">
                        <Link
                          className="font-medium text-slate-900 underline-offset-4 hover:underline"
                          href={`/experiments/${text(item.id)}`}
                        >
                          Experiment {index + 1}
                        </Link>
                      </td>
                      <td className="px-4 py-4 text-slate-600">
                        EMA Sweep Engulfing
                      </td>
                      <td className="px-4 py-4 text-slate-600">
                        {dateLabel(item.tradingStart)}
                        <span className="block text-xs text-slate-400">
                          to {dateLabel(item.tradingEnd)}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <StatusBadge status={status} />
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? metric(object(item.metrics).netReturn)
                          : '—'}
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? metric(object(item.metrics).maxDrawdownPercent)
                          : '—'}
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? metric(object(item.metrics).sharpe)
                          : '—'}
                      </td>
                      <td className="px-4 py-4 tabular-nums">
                        {status === 'COMPLETED'
                          ? metric(object(item.metrics).tradeCount)
                          : '—'}
                      </td>
                      <td className="px-4 py-4 text-slate-600">
                        {dateLabel(item.createdAt)}
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

export function ExperimentForm() {
  const router = useRouter();
  const [options, setOptions] = useState<Json>({});
  const [formError, setFormError] = useState('');
  const [coverage, setCoverage] = useState<Json | null>(null);
  const [validating, setValidating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [strategy, setStrategy] = useState('');
  const [snapshot, setSnapshot] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [capital, setCapital] = useState('10000');
  const [risk, setRisk] = useState('0.01');
  const [slippage, setSlippage] = useState('0');
  const [commission, setCommission] = useState('0');
  useEffect(() => {
    atlasApi
      .configurationOptions()
      .then((value) => {
        const data = object(value);
        setOptions(data);
        const versions = Array.isArray(data.strategyVersions)
          ? data.strategyVersions
          : [];
        const snapshots = Array.isArray(data.datasetSnapshots)
          ? data.datasetSnapshots
          : [];
        setStrategy(text(object(versions[0]).id, ''));
        setSnapshot(text(object(snapshots[0]).id, ''));
      })
      .catch((error) => setFormError(errorMessage(error)));
  }, []);
  const invalidate = () => setCoverage(null);
  const versions = Array.isArray(options.strategyVersions)
    ? options.strategyVersions
    : [];
  const snapshots = Array.isArray(options.datasetSnapshots)
    ? options.datasetSnapshots
    : [];
  const selectedVersion = object(
    versions.find((value) => text(object(value).id) === strategy),
  );
  const validate = async () => {
    setFormError('');
    setValidating(true);
    try {
      setCoverage(
        object(
          await atlasApi.validateCoverage({
            strategyVersionId: strategy,
            datasetSnapshotId: snapshot,
            tradingStart: iso(start),
            tradingEnd: iso(end),
          }),
        ),
      );
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setValidating(false);
    }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    setSubmitting(true);
    try {
      if (!coverage?.valid)
        throw new Error(
          'Validate coverage successfully before starting the Experiment.',
        );
      const created = object(
        await atlasApi.createExperiment({
          strategyVersionId: strategy,
          datasetSnapshotId: snapshot,
          tradingStart: iso(start),
          tradingEnd: iso(end),
          startingCapital: capital,
          riskPerTrade: risk,
          parameters: Object.fromEntries(
            (Array.isArray(selectedVersion.parameterSchema)
              ? selectedVersion.parameterSchema
              : []
            ).map((descriptor) => {
              const item = object(descriptor);
              return [text(item.key), item.default];
            }),
          ),
          slippageTicks: Number(slippage),
          commissionPerUnit: commission,
        }),
      );
      router.push(`/experiments/${text(created.id)}?start=1`);
    } catch (error) {
      setFormError(errorMessage(error));
      setSubmitting(false);
    }
  };
  const blocking = Array.isArray(coverage?.blockingReasons)
    ? coverage.blockingReasons
    : [];
  return (
    <AppShell>
      <section
        aria-labelledby="new-experiment-heading"
        className="max-w-4xl space-y-8"
      >
        <header>
          <Link
            href="/experiments"
            className="mb-5 inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-950"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Experiments
          </Link>
          <h1
            id="new-experiment-heading"
            className="text-3xl font-semibold tracking-tight"
          >
            Run an Experiment
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Use immutable inputs and confirm the requested period is covered
            before Atlas creates a run.
          </p>
        </header>
        {formError && <ErrorPanel message={formError} />}
        <form onSubmit={submit} className="space-y-6">
          <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
            <legend className="px-1 text-base font-medium">
              Methodology and data
            </legend>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                StrategyVersion
                <select
                  required
                  value={strategy}
                  onChange={(e) => {
                    setStrategy(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                >
                  <option value="">Choose a StrategyVersion</option>
                  {versions.map((value) => {
                    const item = object(value);
                    return (
                      <option key={text(item.id)} value={text(item.id)}>
                        {text(item.name, 'EMA Sweep Engulfing')} · v
                        {text(item.version)}
                      </option>
                    );
                  })}
                </select>
              </label>
              <label className="space-y-2 text-sm font-medium">
                DatasetSnapshot
                <select
                  required
                  value={snapshot}
                  onChange={(e) => {
                    setSnapshot(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                >
                  <option value="">Choose a DatasetSnapshot</option>
                  {snapshots.map((value) => {
                    const item = object(value);
                    return (
                      <option key={text(item.id)} value={text(item.id)}>
                        {text(item.fingerprint, 'Snapshot')} ·{' '}
                        {dateLabel(item.coverageStart)}
                      </option>
                    );
                  })}
                </select>
              </label>
            </div>
          </fieldset>
          <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
            <legend className="px-1 text-base font-medium">
              Requested period
            </legend>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                Trading start
                <input
                  required
                  type="datetime-local"
                  value={dateInput(start)}
                  onChange={(e) => {
                    setStart(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                />
              </label>
              <label className="space-y-2 text-sm font-medium">
                Trading end
                <input
                  required
                  type="datetime-local"
                  value={dateInput(end)}
                  onChange={(e) => {
                    setEnd(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                />
              </label>
            </div>
          </fieldset>
          <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
            <legend className="px-1 text-base font-medium">
              Account and Risk
            </legend>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                Starting capital (USD)
                <input
                  required
                  min="1"
                  step="0.01"
                  value={capital}
                  onChange={(e) => {
                    setCapital(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="decimal"
                />
              </label>
              <label className="space-y-2 text-sm font-medium">
                Risk per Trade
                <input
                  required
                  min="0.0001"
                  max="1"
                  step="0.0001"
                  value={risk}
                  onChange={(e) => {
                    setRisk(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="decimal"
                />
              </label>
            </div>
          </fieldset>
          <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
            <legend className="px-1 text-base font-medium">
              Simulation costs
            </legend>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                Adverse slippage (ticks)
                <input
                  required
                  min="0"
                  step="1"
                  value={slippage}
                  onChange={(e) => {
                    setSlippage(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="numeric"
                />
              </label>
              <label className="space-y-2 text-sm font-medium">
                Commission per unit (USD)
                <input
                  required
                  min="0"
                  step="0.0001"
                  value={commission}
                  onChange={(e) => {
                    setCommission(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="decimal"
                />
              </label>
            </div>
            <p className="text-xs text-slate-500">
              M1 execution · MID analysis · BID/ASK execution · Financing
              excluded
            </p>
          </fieldset>
          <section
            aria-live="polite"
            className={`rounded-lg border p-5 ${coverage ? (coverage.valid ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50') : 'border-slate-200 bg-slate-50'}`}
          >
            <div className="flex items-start gap-3">
              <CheckCircle2
                className="mt-0.5 size-5 shrink-0 text-emerald-700"
                aria-hidden
              />
              <div>
                <h2 className="font-medium">Coverage validation</h2>
                {!coverage ? (
                  <p className="mt-1 text-sm text-slate-600">
                    Validate the selected period to check warm-up and immutable
                    snapshot coverage.
                  </p>
                ) : (
                  <>
                    <p className="mt-1 text-sm">
                      {coverage.valid
                        ? 'The selected period is eligible to run.'
                        : 'This period cannot run yet.'}
                    </p>
                    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                      <div>
                        <dt className="text-slate-600">Warm-up</dt>
                        <dd className="font-medium">
                          {text(object(coverage.warmUp).available)} /{' '}
                          {text(object(coverage.warmUp).required)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-slate-600">Open minutes</dt>
                        <dd className="font-medium">
                          {text(object(coverage.counts).memberMinutes)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-slate-600">Gaps</dt>
                        <dd className="font-medium">
                          {Array.isArray(coverage.gaps)
                            ? coverage.gaps.length
                            : 0}
                        </dd>
                      </div>
                    </dl>
                    {blocking.length > 0 && (
                      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm">
                        {blocking.map((reason) => (
                          <li key={String(reason)}>{String(reason)}</li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            </div>
          </section>
          <div className="flex flex-wrap justify-end gap-3">
            <Button
              type="button"
              onClick={validate}
              disabled={validating || !strategy || !snapshot || !start || !end}
            >
              {validating && (
                <LoaderCircle
                  className="mr-2 size-4 animate-spin"
                  aria-hidden
                />
              )}
              Validate coverage
            </Button>
            <Button type="submit" disabled={submitting || !coverage?.valid}>
              {submitting && (
                <LoaderCircle
                  className="mr-2 size-4 animate-spin"
                  aria-hidden
                />
              )}
              Run Experiment
            </Button>
          </div>
        </form>
      </section>
    </AppShell>
  );
}

export function ExperimentStatusPage() {
  const params = useParams<{ experimentId: string }>();
  const search = useSearchParams();
  const id = params.experimentId;
  const instruction = search.get('start') === '1';
  const started = useRef(false);
  const [data, setData] = useState<Json | null>(null);
  const [error, setError] = useState('');
  const [commandError, setCommandError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try {
      const value = object(await atlasApi.getExperiment(id));
      setData(value);
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
  if (loading)
    return (
      <AppShell>
        <p className="text-sm text-slate-600">
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
      <section className="max-w-4xl space-y-8">
        <header>
          <Link
            href="/experiments"
            className="mb-5 inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-950"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Experiments
          </Link>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-slate-500">
                Experiment · {dateLabel(data?.createdAt)}
              </p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">
                EUR/USD historical simulation
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                {dateLabel(data?.tradingStart)} to {dateLabel(data?.tradingEnd)}
              </p>
            </div>
            <StatusBadge status={status} />
          </div>
        </header>
        {commandError && (
          <ErrorPanel message={commandError} retry={() => void run()} />
        )}
        {error && (
          <ErrorPanel
            message={`Status is temporarily unavailable. The Experiment state has not been changed. ${error}`}
            retry={() => void load()}
          />
        )}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-medium">Run status</h2>
          {status === 'PENDING' && (
            <>
              <p className="mt-2 text-sm text-slate-600">
                Configuration is saved. Start the Experiment when ready.
              </p>
              <Button className="mt-4" onClick={() => void run()}>
                <RefreshCw className="mr-2 size-4" aria-hidden />
                Run Experiment
              </Button>
            </>
          )}
          {status === 'RUNNING' && (
            <p className="mt-2 text-sm text-slate-600">
              <Clock3 className="mr-2 inline size-4" aria-hidden />
              Atlas is running the deterministic simulation. This page checks
              status every two seconds; no progress estimate is shown.
            </p>
          )}
          {status === 'FAILED' && (
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">
              <p className="font-medium">
                No trustworthy full result was created.
              </p>
              <p className="mt-1">
                {text(
                  failure.detail,
                  'The Experiment failed before a complete result was available.',
                )}
              </p>
              <p className="mt-3 text-red-800">
                Review the configuration or data, then create a new Experiment.
              </p>
            </div>
          )}
          {status === 'COMPLETED' && (
            <div className="mt-6">
              <EquityResults id={id} data={data ?? {}} />
            </div>
          )}
        </div>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div className="border-t border-slate-200 pt-3">
            <dt className="text-xs font-medium text-slate-500">
              StrategyVersion
            </dt>
            <dd className="mt-1 text-sm">EMA Sweep Engulfing</dd>
          </div>
          <div className="border-t border-slate-200 pt-3">
            <dt className="text-xs font-medium text-slate-500">
              DatasetSnapshot
            </dt>
            <dd className="mt-1 text-sm">Immutable DatasetSnapshot</dd>
          </div>
          <div className="border-t border-slate-200 pt-3">
            <dt className="text-xs font-medium text-slate-500">
              Starting capital
            </dt>
            <dd className="mt-1 text-sm tabular-nums">
              ${text(data?.startingCapital)}
            </dd>
          </div>
          <div className="border-t border-slate-200 pt-3">
            <dt className="text-xs font-medium text-slate-500">
              Risk per Trade
            </dt>
            <dd className="mt-1 text-sm tabular-nums">
              {text(data?.riskPerTrade)}
            </dd>
          </div>
        </dl>
      </section>
    </AppShell>
  );
}

function TradeChart({ chart, levels }: { chart: Json; levels: Json }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let instance: import('lightweight-charts').IChartApi | undefined;
    let observer: ResizeObserver | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({ createChart, CandlestickSeries, LineSeries, ColorType }) => {
        if (!ref.current || disposed) return;
        instance = createChart(ref.current, {
          height: 420,
          layout: {
            background: { type: ColorType.Solid, color: '#ffffff' },
            textColor: '#475569',
          },
          grid: {
            vertLines: { color: '#f1f5f9' },
            horzLines: { color: '#f1f5f9' },
          },
        });
        const candles = instance.addSeries(CandlestickSeries, {
          upColor: '#15803d',
          downColor: '#b91c1c',
          borderVisible: false,
          wickUpColor: '#15803d',
          wickDownColor: '#b91c1c',
        });
        const ema = instance.addSeries(LineSeries, {
          color: '#64748b',
          lineWidth: 1,
          priceLineVisible: false,
        });
        const rows = Array.isArray(chart.candles) ? chart.candles : [];
        const candleData = rows
          .map((raw) => {
            const item = object(raw);
            return {
              time: (new Date(text(item.time, '')).getTime() /
                1000) as import('lightweight-charts').Time,
              open: Number(text(item.open, '0')),
              high: Number(text(item.high, '0')),
              low: Number(text(item.low, '0')),
              close: Number(text(item.close, '0')),
            };
          })
          .filter((item) => Number.isFinite(item.time));
        const emaData = rows
          .map((raw) => {
            const item = object(raw);
            return {
              time: (new Date(text(item.time, '')).getTime() /
                1000) as import('lightweight-charts').Time,
              value: Number(text(item.ema, '0')),
            };
          })
          .filter((item) => Number.isFinite(item.time) && item.value > 0);
        candles.setData(candleData);
        ema.setData(emaData);
        const levelMap = {
          entry: levels.entry,
          exit: levels.exit,
          stop: levels.stop,
          target: levels.target,
        };
        Object.entries(levelMap).forEach(([title, raw]) => {
          const price = Number(text(raw, ''));
          if (Number.isFinite(price) && price > 0) {
            candles.createPriceLine({
              price,
              color:
                title === 'stop'
                  ? '#b91c1c'
                  : title === 'target'
                    ? '#15803d'
                    : '#2563eb',
              lineWidth: 1,
              lineStyle: 2,
              axisLabelVisible: true,
              title,
            });
          }
        });
        instance.timeScale().fitContent();
        observer = new ResizeObserver(() =>
          instance?.applyOptions({ width: ref.current?.clientWidth ?? 0 }),
        );
        observer.observe(ref.current);
      },
    );
    return () => {
      disposed = true;
      observer?.disconnect();
      instance?.remove();
    };
  }, [chart, levels.entry, levels.exit, levels.stop, levels.target]);
  return (
    <div
      ref={ref}
      className="h-[420px] w-full"
      aria-label="Trade candlestick chart with EMA"
    />
  );
}

function Lineage({ data }: { data: Json }) {
  const render = (value: unknown): React.ReactNode => {
    if (Array.isArray(value))
      return (
        <ul className="space-y-2">
          {value.map((item, index) => (
            <li
              key={index}
              className="rounded-md border border-slate-200 bg-white p-3"
            >
              {render(item)}
            </li>
          ))}
        </ul>
      );
    if (value && typeof value === 'object')
      return (
        <dl className="grid gap-x-5 gap-y-2 sm:grid-cols-2">
          {Object.entries(value as Json)
            .filter(([key]) => !key.toLowerCase().endsWith('id'))
            .map(([key, item]) => (
              <div key={key}>
                <dt className="text-xs text-slate-500">
                  {key.replaceAll('_', ' ')}
                </dt>
                <dd className="break-words text-sm">{render(item)}</dd>
              </div>
            ))}
        </dl>
      );
    return <>{text(value)}</>;
  };
  return (
    <div className="space-y-3">
      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <h3 className="font-medium">TradeIntent rationale</h3>
        <div className="mt-3">{render(data.rationale)}</div>
      </section>
      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <h3 className="font-medium">Execution lineage</h3>
        <div className="mt-3 space-y-4">
          <div>
            <h4 className="text-sm font-medium">Risk decisions</h4>
            {render(data.risks)}
          </div>
          <div>
            <h4 className="text-sm font-medium">Orders and events</h4>
            {render(data.orders)}
          </div>
          <div>
            <h4 className="text-sm font-medium">Fills</h4>
            {render(data.fills)}
          </div>
        </div>
      </section>
    </div>
  );
}

export function TradeDetailPage() {
  const params = useParams<{ experimentId: string; sequenceNumber: string }>();
  const [data, setData] = useState<Json | null>(null);
  const [error, setError] = useState('');
  const sequence = Number(params.sequenceNumber);
  const invalidSequence = !Number.isInteger(sequence) || sequence < 1;
  useEffect(() => {
    if (invalidSequence) return;
    atlasApi
      .getTrade(params.experimentId, sequence)
      .then((value) => setData(object(value)))
      .catch((reason) => setError(errorMessage(reason)));
  }, [invalidSequence, params.experimentId, sequence]);
  if (invalidSequence || error)
    return (
      <AppShell>
        <ErrorPanel
          message={
            invalidSequence ? 'This Trade sequence is not valid.' : error
          }
          retry={() => window.location.reload()}
        />
      </AppShell>
    );
  if (!data)
    return (
      <AppShell>
        <p className="text-sm text-slate-600">
          <LoaderCircle
            className="mr-2 inline size-4 animate-spin"
            aria-hidden
          />
          Loading Trade…
        </p>
      </AppShell>
    );
  const summary = object(data.summary);
  const chart = object(data.chart);
  const omitted = object(chart.omitted_range);
  const hasOmitted = Object.keys(omitted).length > 0;
  const ambiguous = summary.ambiguous === true;
  const levels = {
    entry: summary.entry_price,
    exit: summary.exit_price,
    stop: data.initial_stop,
    target: data.target,
  };
  return (
    <AppShell>
      <section className="space-y-8">
        <header>
          <Link
            href={`/experiments/${params.experimentId}`}
            className="mb-5 inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-950"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Back to Experiment
          </Link>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-slate-500">
                EUR/USD · EMA Sweep Engulfing · OANDA Practice
              </p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">
                Trade {text(summary.sequence_number)}
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                {text(summary.direction)} · {dateLabel(summary.opened_at)} →{' '}
                {dateLabel(summary.closed_at)}
              </p>
            </div>
            <span className="status rounded-full border border-slate-200 bg-white px-2.5 py-1 text-slate-700">
              Historical Experiment
            </span>
          </div>
        </header>
        <dl className="grid gap-x-6 gap-y-5 border-y border-slate-200 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Net P&L"
            value={{ state: 'VALUE', value: text(summary.net_pnl) }}
            format="money"
          />
          <MetricCard
            label="R multiple"
            value={{ state: 'VALUE', value: text(summary.r_multiple) }}
          />
          <div>
            <dt className="text-xs text-slate-500">Entry / exit</dt>
            <dd className="mt-1 tabular-nums">
              {text(summary.entry_price)} → {text(summary.exit_price)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Exit reason</dt>
            <dd className="mt-1">{text(summary.exit_reason)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Initial stop / target</dt>
            <dd className="mt-1 tabular-nums">
              {text(data.initial_stop)} / {text(data.target)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Ambiguity</dt>
            <dd className="mt-1">
              {ambiguous
                ? 'Ambiguous intrabar resolution — Stop-first policy applied.'
              : 'None recorded'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Financing</dt>
            <dd className="mt-1 font-medium">
              {text(data.financing_disclosure)}
            </dd>
          </div>
        </dl>
        <section>
          <h2 className="text-lg font-semibold">Trade context</h2>
          <p className="mt-1 text-sm text-slate-600">
            Canonical M15 MID candles and EMA 100 from the immutable
            DatasetSnapshot. Atlas supplied the setup markers; the browser does
            not infer Strategy identity.
          </p>
          {hasOmitted && (
            <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Chart omits a range from {dateLabel(omitted.start)} to{' '}
              {dateLabel(omitted.end)} to keep the focused context bounded.
            </p>
          )}
          <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
            <TradeChart chart={chart} levels={levels} />
          </div>
        </section>
        <Lineage data={data} />
      </section>
    </AppShell>
  );
}
