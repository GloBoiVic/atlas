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
import { AppShell } from './app-shell';
import { Button } from './ui/button';
import { UtcDateTimePicker } from './utc-date-time-picker';
import {
  ApiError,
  ApiTransportTimeoutError,
  ApiUnavailableError,
  atlasApi,
} from '../lib/api-client';
import {
  formatChartTime,
  formatChartTick,
  formatInstant,
  parseUtcInput,
  utcInputFromInstant,
} from '../lib/time';
import { useDisplayTimeZone } from '../app/providers';

type Json = Record<string, unknown>;
type Status = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
type ParameterValues = Record<string, string>;
type ChartPoint = { time: import('lightweight-charts').Time };

// Lightweight Charts rejects non-ascending or duplicate timestamps.
export const strictlyAscending = <T extends ChartPoint>(points: T[]): T[] => {
  const sorted = [...points].sort((a, b) => Number(a.time) - Number(b.time));
  return sorted.filter(
    (point, index) =>
      index === 0 || Number(point.time) > Number(sorted[index - 1].time),
  );
};

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
const dateLabel = (
  value: unknown,
  zone?: Parameters<typeof formatInstant>[1],
) => formatInstant(value, zone);
const dateInput = (value: string) => utcInputFromInstant(value);
const iso = (value: string) => parseUtcInput(value);
const utcDate = (value: string) => {
  const parsed = parseUtcInput(value);
  return parsed ? new Date(parsed) : null;
};
const quarterHourNow = () => {
  const now = new Date();
  now.setUTCMinutes(Math.floor(now.getUTCMinutes() / 15) * 15, 0, 0);
  return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}T${String(now.getUTCHours()).padStart(2, '0')}:${String(now.getUTCMinutes()).padStart(2, '0')}`;
};
const snapshotLabel = (item: Json) => {
  const integrity = object(item.integrity);
  const count = Number(
    item.barCount ?? integrity.barCount ?? integrity.bar_count,
  );
  if (!Number.isFinite(count)) return text(item.fingerprint, 'Snapshot');
  const compact = (value: unknown) =>
    formatInstant(value, 'UTC').replace(/ UTC$/, '');
  const policy = text(
    integrity.policyVersion ??
      integrity.policy_version ??
      integrity.sessionPolicy ??
      integrity.session_policy,
    'policy unknown',
  );
  return `EUR/USD · ${compact(item.coverageStart)}→${compact(item.coverageEnd)} UTC · ${count} bars · ${text(item.fingerprint, '').slice(0, 8)} · ${policy}`;
};
const diagnosticLabel = (value: unknown) => {
  const item = object(value);
  const components = Array.isArray(item.missing_components)
    ? item.missing_components.map(String).join(', ')
    : '';
  return `${text(item.reason, 'DIAGNOSTIC')} · ${text(item.policy_version, 'policy unknown')}${components ? ` · ${components}` : ''}`;
};
const metric = (value: unknown) => {
  const data = object(value);
  if (data.state === 'INFINITE') return '∞';
  return data.state === 'VALUE' ? text(data.value) : '—';
};
const metricState = (value: unknown) => object(value);
const errorMessage = (error: unknown) =>
  typeof error === 'string'
    ? error
    : error instanceof Error
      ? error.message
      : 'Atlas could not complete that request.';

const productNextAction = (error: ApiError) => {
  const rawFields = object(error.details).fields;
  const fields = object(rawFields);
  const fieldKeys =
    rawFields && typeof rawFields === 'object' && !Array.isArray(rawFields)
      ? Object.keys(fields)
      : [];
  if (fieldKeys.some((key) => key === 'body.strategyVersionId')) {
    return 'Pick a StrategyVersion first — still loading';
  }
  if (
    fieldKeys.some(
      (key) =>
        key.includes('body.tradingStart') || key.includes('body.tradingEnd'),
    )
  ) {
    return 'Enter a positive 15-minute-aligned UTC range using 00/15/30/45.';
  }
  switch (error.code) {
    case 'TRADING_PERIOD_NOT_15M_ALIGNED':
    case 'NOT_15M_ALIGNED':
      return 'Not 15-minute aligned — use 00/15/30/45 in UTC.';
    case 'EXCEEDS_90_DAYS':
    case 'LOAD_RANGE_TOO_LARGE':
      return 'That range exceeds 90 days — try ≤90d or split it.';
    case 'TOO_MANY_WINDOWS':
    case 'LOAD_PLAN_TOO_LARGE':
      return 'That range needs fewer windows — load ≤40 missing windows or split it.';
    case 'FRONTIER_EXCEEDS_COMPLETED_MINUTE':
    case 'FRONTIER':
      return 'End is in the future — pick ≤ now.';
    case 'STRATEGY_VERSION_NOT_FOUND':
      return 'Pick a StrategyVersion from the dropdown.';
    case 'HISTORICAL_LOAD_ACTIVE':
      return 'A load is already active — Atlas will attach to its durable status; refresh status if needed.';
    case 'OANDA_UNAVAILABLE':
      return 'OANDA Practice is unavailable — wait and retry when the provider is healthy.';
    case 'HTTP_404':
      return 'Historical data service not ready — run `uv run alembic upgrade head` and restart the API (backend on old branch).';
    default:
      return undefined;
  }
};

const scalarFields = (error: unknown) => {
  const fields = object(object(error).details).fields;
  if (!fields || typeof fields !== 'object' || Array.isArray(fields)) return [];
  return Object.entries(fields as Json)
    .filter(
      ([, value]) =>
        value === null ||
        ['string', 'number', 'boolean'].includes(typeof value),
    )
    .slice(0, 8) as [string, string | number | boolean | null][];
};
const parameterDefaults = (version: unknown): ParameterValues => {
  const schema = Array.isArray(object(version).parameterSchema)
    ? (object(version).parameterSchema as unknown[])
    : [];
  return Object.fromEntries(
    schema.map((value) => {
      const descriptor = object(value);
      return [text(descriptor.key, ''), text(descriptor.default, '')];
    }),
  );
};

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
  error,
  retry,
}: {
  message?: string;
  error?: unknown;
  retry?: () => void;
}) {
  const source = error ?? message ?? '';
  const apiError = source instanceof ApiError ? source : null;
  const nextAction = apiError ? productNextAction(apiError) : undefined;
  const fields = scalarFields(source);
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900"
    >
      <AlertCircle aria-hidden className="mt-0.5 size-5 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">
          {nextAction ? 'Action needed' : 'Request needs attention'}
        </p>
        <p className="mt-1 text-red-800">
          {apiError?.message ?? errorMessage(source)}
        </p>
        {nextAction && (
          <p className="mt-1 font-medium text-red-900">{nextAction}</p>
        )}
        {apiError && (
          <p className="mt-1 text-xs text-red-700">Code: {apiError.code}</p>
        )}
        {fields.length > 0 && (
          <details className="mt-3 text-xs text-red-800">
            <summary className="cursor-pointer font-medium">Details</summary>
            <dl className="mt-2 space-y-1">
              {fields.map(([key, value]) => (
                <div key={key}>
                  <dt className="inline font-medium">{key}: </dt>
                  <dd className="inline">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
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
  const { timeZone } = useDisplayTimeZone();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let chart: import('lightweight-charts').IChartApi | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({ createChart, LineSeries, ColorType }) => {
        // Lightweight Charts requires a real canvas; leave the host untouched
        // when a non-browser renderer cannot provide one (for example jsdom).
        // Test doubles remain usable because they expose no required arity.
        if (
          createChart.length > 0 &&
          typeof navigator !== 'undefined' &&
          navigator.userAgent.includes('jsdom')
        )
          return;
        if (!ref.current || disposed) return;
        chart = createChart(ref.current, {
          height: 260,
          width: Math.max(ref.current.clientWidth, 1),
          layout: {
            background: { type: ColorType.Solid, color: '#ffffff' },
            textColor: '#475569',
          },
          grid: {
            vertLines: { color: '#f1f5f9' },
            horzLines: { color: '#f1f5f9' },
          },
          rightPriceScale: { borderColor: '#e2e8f0' },
          localization: {
            timeFormatter: (time: number) => formatChartTime(time, timeZone),
          },
          timeScale: {
            borderColor: '#e2e8f0',
            tickMarkFormatter: (time: number) =>
              formatChartTick(time, timeZone),
          },
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
        if (data.length) series.setData(strictlyAscending(data));
        chart.timeScale().fitContent();
        const observer = new ResizeObserver(() =>
          chart?.applyOptions({
            width: Math.max(ref.current?.clientWidth ?? 0, 1),
          }),
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
  }, [kind, points, timeZone]);
  return (
    <div ref={ref} className="h-[260px] w-full" aria-label={`${kind} chart`} />
  );
}

function StateDisclosure({ data }: { data: Json }) {
  const { timeZone } = useDisplayTimeZone();
  const config = object(data.simulationConfig);
  const quality = object(data.resultQuality);
  const gaps = Array.isArray(data.gapDecisions) ? data.gapDecisions : [];
  const provenance = object(data.provenance);
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
            {dateLabel(data.tradingStart, timeZone)} →{' '}
            {dateLabel(data.tradingEnd, timeZone)}
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
            Native M15 MID analysis · sparse{' '}
            {text(config.execution_resolution, 'M1')} BID/ASK
            <span className="block text-xs text-slate-600">
              Entry only in the immediately following bucket [frontier, frontier
              + 1 minute)
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Financing</dt>
          <dd className="font-medium">FINANCING EXCLUDED</dd>
        </div>
        <div>
          <dt className="text-slate-500">DatasetSnapshot</dt>
          <dd>
            {text(provenance.snapshotSchema, 'Immutable snapshot')} · immutable
            provenance retained
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Model</dt>
          <dd>{text(data.modelVersion, 'V2')}</dd>
          <dd className="text-xs text-slate-600">
            Result schema {text(data.resultSchemaVersion, 'V2')}
          </dd>
        </div>
      </dl>
      {Boolean(quality.value) && (
        <p className="mt-5 text-sm text-slate-700">
          Result quality: <strong>{text(quality.value)}</strong>
        </p>
      )}
      {gaps.length > 0 && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          <strong>Historical data gaps disclosed:</strong> {gaps.length}{' '}
          persisted gap decision{gaps.length === 1 ? '' : 's'}. Missing
          observations are not shown as continuous prices.
        </div>
      )}
      {gaps.length === 0 && Boolean(data.resultQuality) && (
        <p className="mt-4 text-sm text-slate-700">
          No execution gaps affected this result.
        </p>
      )}
      <p className="mt-5 text-xs leading-5 text-slate-600">
        Spread is embedded in BID/ASK execution and is not double-counted. Chart
        sampling, if disclosed above, is presentation-only and never feeds
        metrics.
      </p>
    </div>
  );
}

function EquityResults({ id, data }: { id: string; data: Json }) {
  const { timeZone } = useDisplayTimeZone();
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
      <PriceAnalysisChart id={id} />
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
          <p className="mt-1 text-xs text-slate-500">
            Times shown in {timeZone}. {pointsRange(points, timeZone)}
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

function PriceAnalysisChart({ id }: { id: string }) {
  const { timeZone } = useDisplayTimeZone();
  const [analysis, setAnalysis] = useState<Json | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    atlasApi
      .getPriceAnalysis(id)
      .then((value) => {
        if (active) setAnalysis(object(value));
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [id]);

  const diagnostics = object(analysis?.diagnostics);
  const tradingWindow = object(analysis?.tradingWindow);
  const truncated = diagnostics.truncated === true;
  const omitted = object(diagnostics.omittedRange);
  const omittedDescription = truncated
    ? `${text(diagnostics.omittedM15Count, '0')} M15 candles and ${text(diagnostics.omittedTradeCount, '0')} Trades omitted${omitted.start && omitted.end ? ` · ${formatChartTime(new Date(String(omitted.start)).getTime() / 1000, timeZone)} → ${formatChartTime(new Date(String(omitted.end)).getTime() / 1000, timeZone)}` : ''}.`
    : '';

  return (
    <section aria-labelledby="price-analysis-heading" className="space-y-4">
      <div>
        <h2 id="price-analysis-heading" className="text-lg font-semibold">
          Price analysis
        </h2>
        <p className="text-sm text-slate-600">
          {text(
            object(analysis?.provenance).analyticalSeries,
            'M15 analytical',
          )}{' '}
          — persisted analytical M15 candles and the Experiment’s authoritative
          EMA. Times shown in {timeZone}.
        </p>
      </div>
      {error ? (
        <ErrorPanel message={error} retry={() => window.location.reload()} />
      ) : !analysis ? (
        <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
          Loading price analysis…
        </div>
      ) : (
        <>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <PriceAnalysisCanvas analysis={analysis} timeZone={timeZone} />
            {Array.isArray(analysis.trades) && analysis.trades.length === 0 && (
              <p className="border-t border-slate-100 px-2 pt-3 text-sm text-slate-700">
                No trades were generated in this period.
              </p>
            )}
          </div>
          <div
            className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-600"
            aria-label="Price analysis legend"
          >
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-slate-500" />
              EMA
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-blue-600" />
              Window
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-emerald-600" />
              Entry / target
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-red-600" />
              Exit / stop
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-violet-600" />
              Strategy facts
            </span>
          </div>
          {truncated && (
            <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
              <strong>Chart truncated.</strong> {omittedDescription} This view
              does not cover the full result period.
            </p>
          )}
        </>
      )}
      {analysis ? (
        tradingWindow.start && tradingWindow.end ? (
          <p className="text-xs text-slate-500">
            Trading window:{' '}
            {formatChartTime(
              new Date(String(tradingWindow.start)).getTime() / 1000,
              timeZone,
            )}{' '}
            →{' '}
            {formatChartTime(
              new Date(String(tradingWindow.end)).getTime() / 1000,
              timeZone,
            )}
          </p>
        ) : null
      ) : null}
    </section>
  );
}

function PriceAnalysisCanvas({
  analysis,
  timeZone,
}: {
  analysis: Json;
  timeZone: Parameters<typeof formatInstant>[1];
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let instance: import('lightweight-charts').IChartApi | undefined;
    let observer: ResizeObserver | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({
        createChart,
        CandlestickSeries,
        LineSeries,
        ColorType,
        createSeriesMarkers,
      }) => {
        if (
          createChart.length > 0 &&
          typeof navigator !== 'undefined' &&
          navigator.userAgent.includes('jsdom')
        )
          return;
        if (!ref.current || disposed) return;
        instance = createChart(ref.current, {
          height: 440,
          width: Math.max(ref.current.clientWidth, 1),
          layout: {
            background: { type: ColorType.Solid, color: '#ffffff' },
            textColor: '#475569',
          },
          grid: {
            vertLines: { color: '#f1f5f9' },
            horzLines: { color: '#f1f5f9' },
          },
          localization: {
            timeFormatter: (time: number) => formatChartTime(time, timeZone),
          },
          timeScale: {
            tickMarkFormatter: (time: number) =>
              formatChartTick(time, timeZone),
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
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        const toTime = (value: unknown) => {
          const epoch = new Date(String(value)).getTime() / 1000;
          return Number.isFinite(epoch)
            ? (epoch as import('lightweight-charts').Time)
            : null;
        };
        const rows = Array.isArray(analysis.m15) ? analysis.m15 : [];
        const candleData = rows
          .map((raw) => {
            const item = object(raw);
            const time = toTime(item.t);
            return time === null
              ? null
              : {
                  time,
                  open: Number(item.o),
                  high: Number(item.h),
                  low: Number(item.l),
                  close: Number(item.c),
                };
          })
          .filter(
            (
              item,
            ): item is {
              time: import('lightweight-charts').Time;
              open: number;
              high: number;
              low: number;
              close: number;
            } =>
              item !== null &&
              [item.open, item.high, item.low, item.close].every(
                Number.isFinite,
              ),
          );
        const emaData = (Array.isArray(analysis.ema) ? analysis.ema : [])
          .map((raw) => {
            const item = object(raw);
            const time = toTime(item.t);
            const value = Number(item.v);
            return time === null || !Number.isFinite(value)
              ? null
              : { time, value };
          })
          .filter(
            (
              item,
            ): item is {
              time: import('lightweight-charts').Time;
              value: number;
            } => item !== null,
          );
        candles.setData(strictlyAscending(candleData));
        ema.setData(strictlyAscending(emaData));
        const markerItems: Array<{
          time: import('lightweight-charts').Time;
          position: 'aboveBar' | 'belowBar';
          color: string;
          shape: 'circle' | 'arrowUp' | 'arrowDown';
          text: string;
        }> = [];
        const tradingWindow = object(analysis.tradingWindow);
        (
          [
            ['start', tradingWindow.start],
            ['end', tradingWindow.end],
          ] as const
        ).forEach(([label, value]) => {
          const time = toTime(value);
          if (time !== null)
            markerItems.push({
              time,
              position: 'aboveBar',
              color: '#2563eb',
              shape: 'circle',
              text: `${label === 'start' ? 'Start' : 'End'} · ${formatChartTime(Number(time), timeZone)}`,
            });
        });
        const tradeRows = Array.isArray(analysis.trades) ? analysis.trades : [];
        tradeRows.forEach((raw) => {
          const trade = object(raw);
          const sequence = text(trade.sequence, '?');
          [
            ['entry', trade.entry, 'arrowUp', 'belowBar', '#15803d'],
            ['exit', trade.exit, 'arrowDown', 'aboveBar', '#b91c1c'],
          ].forEach(([label, point, shape, position, color]) => {
            const item = object(point);
            const time = toTime(item.t);
            if (time !== null)
              markerItems.push({
                time,
                position: position as 'aboveBar' | 'belowBar',
                color: color as string,
                shape: shape as 'arrowUp' | 'arrowDown',
                text: `Trade ${sequence} ${label}`,
              });
          });
        });
        createSeriesMarkers(
          candles,
          markerItems.sort((a, b) => Number(a.time) - Number(b.time)),
        );
        const addFact = (raw: unknown, color: string) => {
          const fact = object(raw);
          ['reference', 'sweep', 'confirmation'].forEach((kind) => {
            const stage = object(fact[kind]);
            const time = toTime(stage.t);
            const low = Number(stage.low);
            const high = Number(stage.high);
            if (
              time !== null &&
              Number.isFinite(low) &&
              Number.isFinite(high)
            ) {
              const line = instance?.addSeries(LineSeries, {
                color,
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
              });
              line?.setData(
                strictlyAscending([
                  { time, value: low },
                  {
                    time: (Number(time) +
                      0.001) as import('lightweight-charts').Time,
                    value: high,
                  },
                ]),
              );
            }
          });
        };
        (Array.isArray(analysis.reference) ? analysis.reference : []).forEach(
          (fact) => addFact(fact, '#7c3aed'),
        );
        tradeRows.forEach((raw) => {
          const trade = object(raw);
          ['stop', 'target'].forEach((kind) => {
            const level = object(trade[kind]);
            const from = toTime(level.from);
            const to = toTime(level.to);
            const price = Number(level.price);
            if (from !== null && to !== null && Number.isFinite(price)) {
              const line = instance?.addSeries(LineSeries, {
                color: kind === 'stop' ? '#b91c1c' : '#15803d',
                lineWidth: 1,
                lineStyle: 2,
                priceLineVisible: false,
                lastValueVisible: false,
              });
              line?.setData(
                strictlyAscending([
                  { time: from, value: price },
                  {
                    time:
                      Number(to) === Number(from)
                        ? ((Number(to) +
                            0.001) as import('lightweight-charts').Time)
                        : to,
                    value: price,
                  },
                ]),
              );
            }
          });
        });
        instance.timeScale().fitContent();
        observer = new ResizeObserver(() =>
          instance?.applyOptions({
            width: Math.max(ref.current?.clientWidth ?? 0, 1),
          }),
        );
        observer.observe(ref.current);
      },
    );
    return () => {
      disposed = true;
      observer?.disconnect();
      instance?.remove();
    };
  }, [analysis, timeZone]);
  return (
    <div
      ref={ref}
      className="h-[440px] w-full"
      aria-label="Experiment price analysis chart"
    />
  );
}

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
          <div className="flex flex-wrap gap-3">
            <Link
              href="/experiments/new"
              className="inline-flex min-h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
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
              className={`inline-flex min-h-10 items-center rounded-md border px-4 text-sm font-medium ${selected.length >= 2 && selected.length <= 4 ? 'border-slate-300 bg-white text-slate-900 hover:bg-slate-50' : 'cursor-not-allowed border-slate-200 text-slate-400'}`}
            >
              Compare selected{' '}
              <span className="ml-1 text-xs">({selected.length}/4)</span>
            </Link>
          </div>
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
                            className="size-4 accent-blue-700"
                          />
                        ) : (
                          <span
                            className="text-xs text-slate-400"
                            title="Only COMPLETED Experiments can be compared"
                          >
                            Not eligible
                          </span>
                        )}
                      </td>
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
                        {dateLabel(item.tradingStart, timeZone)}
                        <span className="block text-xs text-slate-400">
                          to {dateLabel(item.tradingEnd, timeZone)}
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

export function ExperimentForm() {
  const router = useRouter();
  const [options, setOptions] = useState<Json>({});
  const [formError, setFormError] = useState<unknown>('');
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
  const [parameters, setParameters] = useState<ParameterValues>({});
  const [capability, setCapability] = useState<Json | null>(null);
  const [historicalLoad, setHistoricalLoad] = useState<Json | null>(null);
  const [loadMessage, setLoadMessage] = useState<unknown>('');
  const [pollFailures, setPollFailures] = useState(0);
  const [pollPaused, setPollPaused] = useState(false);
  const [inventory, setInventory] = useState<Json | null>(null);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [loadStartedAt, setLoadStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const historicalLoadId = useRef('');
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
        const available = versions.filter(
          (value) => object(value).executionAvailable !== false,
        );
        const preferred = [...available].sort(
          (a, b) => Number(object(b).version) - Number(object(a).version),
        )[0];
        setStrategy(text(object(preferred).id, ''));
        setParameters(parameterDefaults(preferred));
        setSnapshot(text(object(snapshots[0]).id, ''));
      })
      .catch((error) => setFormError(error))
      .finally(() => setOptionsLoading(false));
  }, []);
  const refreshOptions = useCallback(async () => {
    const value = object(await atlasApi.configurationOptions());
    setOptions(value);
    const nextSnapshots = Array.isArray(value.datasetSnapshots)
      ? value.datasetSnapshots
      : [];
    return nextSnapshots;
  }, []);
  useEffect(() => {
    void Promise.allSettled([
      atlasApi.historicalCapability(),
      atlasApi.activeHistoricalLoad(),
    ]).then(([cap, active]) => {
      if (cap.status === 'fulfilled') setCapability(object(cap.value));
      else {
        // Backend on old branch (before 0008) has no /historical-data/* → 404 HTTP_404. Treat as unavailable, not a red error on reload.
        const reason = cap.reason;
        if (
          reason instanceof ApiError &&
          (reason.code === 'HTTP_404' || reason.status === 404)
        )
          setCapability({ available: false });
      }
      if (active.status === 'fulfilled') {
        const value = active.value === null ? null : object(active.value);
        setHistoricalLoad(value);
        historicalLoadId.current = text(object(value).id, '');
        const s = text(object(value).status, '');
        if (s === 'PENDING' || s === 'RUNNING') setLoadStartedAt(Date.now());
      } else {
        // Initial page load never shows a red ErrorPanel — missing active load is normal (null), old-backend 404 is handled via capability.
        // Real explicit-load errors are surfaced only after you click Load/Validate.
      }
    });
  }, []);
  const pollLoad = useCallback(async (id: string) => {
    if (!id || historicalLoadId.current !== id) return null;
    try {
      const value = object(await atlasApi.historicalLoadStatus(id));
      if (historicalLoadId.current !== id) return null;
      setHistoricalLoad(value);
      setPollFailures(0);
      return value;
    } catch (error) {
      if (historicalLoadId.current !== id) return null;
      if (error instanceof ApiUnavailableError)
        setPollFailures((value) => value + 1);
      else setLoadMessage(error);
      return null;
    }
  }, []);
  const status = text(historicalLoad?.status, '');
  useEffect(() => {
    if (
      !historicalLoad ||
      (status !== 'PENDING' && status !== 'RUNNING') ||
      pollPaused ||
      pollFailures >= 3
    )
      return;
    const timer = window.setInterval(
      () => void pollLoad(historicalLoadId.current),
      1000,
    );
    return () => window.clearInterval(timer);
    // The request id is deliberately read from the ref: status payload objects change every tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, pollPaused, pollFailures]);
  // Elapsed timer for active loads — shows user the 30-60s wait is normal
  useEffect(() => {
    if (status !== 'PENDING' && status !== 'RUNNING') {
      if (status !== 'COMPLETED') {
        const tid = window.setTimeout(() => setElapsed(0), 0);
        return () => window.clearTimeout(tid);
      }
      return;
    }
    if (!loadStartedAt) return;
    const t = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - loadStartedAt) / 1000)),
      1000,
    );
    return () => window.clearInterval(t);
  }, [status, loadStartedAt]);
  const invalidate = () => setCoverage(null);
  const versions = Array.isArray(options.strategyVersions)
    ? options.strategyVersions
    : [];
  const snapshots = Array.isArray(options.datasetSnapshots)
    ? options.datasetSnapshots
    : [];
  const versionsMap = new Map(
    versions.map((value) => [text(object(value).id, ''), object(value)]),
  );
  const selectedVersion = object(
    versions.find((value) => text(object(value).id) === strategy),
  );
  const schema = Array.isArray(selectedVersion.parameterSchema)
    ? selectedVersion.parameterSchema
    : [];
  const requiredHistoricalContextBars = Number(
    selectedVersion.requiredHistoricalContextBars,
  );
  const strategyReady = Boolean(
    strategy &&
    versionsMap.has(strategy) &&
    selectedVersion.executionAvailable !== false &&
    Number.isFinite(requiredHistoricalContextBars) &&
    requiredHistoricalContextBars >= 0,
  );
  const loadStart = (() => {
    const instant = utcDate(start);
    if (!instant || !Number.isFinite(requiredHistoricalContextBars))
      return null;
    instant.setUTCMinutes(
      instant.getUTCMinutes() - requiredHistoricalContextBars * 15,
    );
    return instant;
  })();
  const tradingEnd = utcDate(end);
  const loadDurationDays =
    loadStart && tradingEnd
      ? (tradingEnd.getTime() - loadStart.getTime()) / 86400000
      : null;
  const loadRangeTooLarge = loadDurationDays !== null && loadDurationDays > 90;
  const loadRangeLabel =
    loadStart && tradingEnd
      ? `${formatInstant(loadStart.toISOString(), 'UTC')} → ${formatInstant(tradingEnd.toISOString(), 'UTC')}`
      : 'Choose valid UTC start and end times.';
  const applyPreset = (kind: '1W' | '1M' | '3M') => {
    if (!strategyReady || !Number.isFinite(requiredHistoricalContextBars))
      return;
    const anchor = utcDate(end) ?? utcDate(quarterHourNow()) ?? new Date();
    if (!anchor) return;
    anchor.setUTCMinutes(Math.floor(anchor.getUTCMinutes() / 15) * 15, 0, 0);
    const nextStart = new Date(anchor);
    if (kind === '1W') nextStart.setUTCDate(nextStart.getUTCDate() - 7);
    else
      nextStart.setUTCMonth(nextStart.getUTCMonth() - (kind === '1M' ? 1 : 3));
    const toInput = (date: Date) =>
      `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}T${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}`;
    setEnd(toInput(anchor));
    setStart(toInput(nextStart));
    invalidate();
  };
  useEffect(() => {
    const valid = Boolean(
      strategy && snapshot && iso(start) && iso(end) && iso(start)! < iso(end)!,
    );
    if (!valid) {
      const timer = window.setTimeout(() => setInventory(null), 0);
      return () => window.clearTimeout(timer);
    }
    let current = true;
    const loadingTimer = window.setTimeout(() => setInventoryLoading(true), 0);
    void atlasApi
      .validateCoverage({
        strategyVersionId: strategy,
        datasetSnapshotId: snapshot,
        tradingStart: iso(start)!,
        tradingEnd: iso(end)!,
      })
      .then((value) => {
        if (current) setInventory(object(value));
      })
      .catch(() => {
        if (current) setInventory(null);
      })
      .finally(() => {
        if (current) setInventoryLoading(false);
      });
    return () => {
      current = false;
      window.clearTimeout(loadingTimer);
    };
  }, [strategy, snapshot, start, end]);
  const parameterErrors = Object.fromEntries(
    schema.flatMap((value) => {
      const descriptor = object(value);
      const key = text(descriptor.key, '');
      const raw = parameters[key] ?? '';
      if (!key || raw.trim() === '') return [[key, 'Enter a value.']];
      const kind = text(descriptor.type, '');
      const parsed = kind === 'integer' ? Number(raw) : Number(raw);
      if (
        !Number.isFinite(parsed) ||
        (kind === 'integer' && !Number.isInteger(parsed))
      ) {
        return [
          [
            key,
            kind === 'integer'
              ? 'Enter a whole number.'
              : 'Enter a finite decimal.',
          ],
        ];
      }
      const minimum = Number(descriptor.min);
      const maximum = Number(descriptor.max);
      if (Number.isFinite(minimum) && parsed < minimum)
        return [[key, `Must be at least ${text(descriptor.min)}.`]];
      if (Number.isFinite(maximum) && parsed > maximum)
        return [[key, `Must be at most ${text(descriptor.max)}.`]];
      return [];
    }),
  );
  const loadActive = ['PENDING', 'RUNNING'].includes(
    text(historicalLoad?.status, ''),
  );
  const loadBlocksCreation = ['PENDING', 'RUNNING', 'FAILED'].includes(
    text(historicalLoad?.status, ''),
  );
  const progress = object(historicalLoad?.progress);
  const loadCoverage = object(historicalLoad?.coverage);
  const visibleDiagnostics = (value: unknown): unknown[] => {
    const diagnostics = object(value).diagnostics;
    return Array.isArray(diagnostics)
      ? (diagnostics as unknown[]).slice(0, 5)
      : [];
  };
  const validate = async (snapshotValue = snapshot) => {
    setFormError('');
    setValidating(true);
    try {
      setCoverage(
        object(
          await atlasApi.validateCoverage({
            strategyVersionId: strategy,
            datasetSnapshotId: snapshotValue,
            tradingStart: iso(start) ?? '',
            tradingEnd: iso(end) ?? '',
          }),
        ),
      );
    } catch (error) {
      setFormError(error);
    } finally {
      setValidating(false);
    }
  };
  useEffect(() => {
    if (text(historicalLoad?.status, '') !== 'COMPLETED') return;
    const period = `${dateLabel(historicalLoad?.tradingStart, 'UTC')} → ${dateLabel(historicalLoad?.tradingEnd, 'UTC')}`;
    const label = text(
      object(historicalLoad?.snapshot) &&
        snapshotLabel(object(object(historicalLoad?.snapshot))),
      text(historicalLoad?.displayLabel, 'Data ready'),
    );
    toast.success(`✓ Data ready — ${period}`, {
      description: `${label} selected. Validate and hit Run Experiment.`,
      duration: 6000,
    });
    // This asynchronous completion handler synchronizes durable API state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshOptions().then((items) => {
      const id = text(object(historicalLoad?.snapshot).id, '');
      if (id && items.some((item) => text(object(item).id) === id))
        setSnapshot(id);
      void validate(id);
    });
    // Completion is a durable event; this effect intentionally runs once per request id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historicalLoad?.status, historicalLoad?.id]);
  const loadHistoricalData = async () => {
    setFormError('');
    setLoadMessage('');
    setCoverage(null);
    setPollPaused(false);
    setPollFailures(0);
    if (!strategyReady) {
      setLoadMessage(
        new ApiError(
          422,
          'STRATEGY_VERSION_NOT_FOUND',
          'Pick a StrategyVersion first — still loading',
        ),
      );
      return;
    }
    const tradingStart = iso(start);
    const tradingEnd = iso(end);
    if (!tradingStart || !tradingEnd || tradingStart >= tradingEnd) {
      setLoadMessage('Enter a valid 15-minute UTC period before loading data.');
      return;
    }
    if (loadRangeTooLarge) {
      setLoadMessage(
        'Shorten the period so the required-context-inclusive load range is 90 days or less.',
      );
      return;
    }
    try {
      const value = object(
        await atlasApi.createHistoricalLoad({
          strategyVersionId: strategy,
          tradingStart,
          tradingEnd,
        }),
      );
      historicalLoadId.current = text(value.id, '');
      setHistoricalLoad(value);
      setLoadStartedAt(Date.now());
      setElapsed(0);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const id = text(object(error.details).requestId, '');
        if (id) {
          historicalLoadId.current = id;
          try {
            const attached = object(await atlasApi.historicalLoadStatus(id));
            setHistoricalLoad(attached);
            const s = text(attached.status, '');
            if (s === 'PENDING' || s === 'RUNNING') {
              setLoadStartedAt(Date.now());
              setElapsed(0);
            }
          } catch (attachError) {
            setLoadMessage(attachError);
          }
        } else setLoadMessage(error);
      } else setLoadMessage(error);
    }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    setSubmitting(true);
    try {
      if (Object.keys(parameterErrors).length > 0)
        throw new Error(
          'Resolve the parameter errors before starting the Experiment.',
        );
      if (!coverage?.valid)
        throw new Error(
          'Validate coverage successfully before starting the Experiment.',
        );
      if (loadBlocksCreation)
        throw new Error(
          'Historical data loading must complete successfully before starting the Experiment.',
        );
      const tradingStart = iso(start);
      const tradingEnd = iso(end);
      if (!tradingStart || !tradingEnd)
        throw new Error('Enter a valid 15-minute UTC period.');
      const created = object(
        await atlasApi.createExperiment({
          strategyVersionId: strategy,
          datasetSnapshotId: snapshot,
          tradingStart,
          tradingEnd,
          startingCapital: capital,
          riskPerTrade: risk,
          parameters: Object.fromEntries(
            schema.map((descriptor) => {
              const item = object(descriptor);
              const key = text(item.key, '');
              return [
                key,
                text(item.type) === 'integer'
                  ? Number(parameters[key])
                  : parameters[key],
              ];
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
  const selectedSnapshot = object(
    snapshots.find((value) => text(object(value).id, '') === snapshot) ??
      object(historicalLoad?.snapshot),
  );
  const selectedSnapshotIntegrity = object(selectedSnapshot.integrity);
  const proofSource = object(historicalLoad?.source ?? capability);
  const proofFingerprint = text(selectedSnapshot.fingerprint, 'awaiting data');
  const proofStatus = historicalLoad
    ? text(historicalLoad.status, 'awaiting data')
    : capability?.available === true
      ? 'idle'
      : capability?.available === false
        ? 'unavailable'
        : 'awaiting data';
  const proofLine = `Proof: ${text(proofSource.provider, 'OANDA Practice')} ${text(proofSource.instrument, 'EUR/USD')} · native M15 MID + sparse M1 BID/ASK → immutable snapshot ${proofFingerprint === 'awaiting data' ? proofFingerprint : proofFingerprint.slice(0, 8)} · load ${proofStatus}`;
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
        {Boolean(formError) && <ErrorPanel error={formError} />}
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
                  disabled={loadActive}
                  value={strategy}
                  onChange={(e) => {
                    const version = versions.find(
                      (value) => text(object(value).id) === e.target.value,
                    );
                    setStrategy(e.target.value);
                    setParameters(parameterDefaults(version));
                    invalidate();
                  }}
                  className="form-control"
                >
                  <option value="">Choose a StrategyVersion</option>
                  {versions.map((value) => {
                    const item = object(value);
                    return (
                      <option
                        key={text(item.id)}
                        value={text(item.id)}
                        disabled={item.executionAvailable === false}
                      >
                        {text(
                          item.displayName,
                          `${text(item.name, 'EMA Sweep Engulfing')} · v${text(item.version)}`,
                        )}
                        {item.executionAvailable === false
                          ? ' · unavailable'
                          : ''}
                      </option>
                    );
                  })}
                </select>
                {optionsLoading && strategy === '' && (
                  <span className="block text-xs font-normal text-slate-500">
                    Loading StrategyVersions…
                  </span>
                )}
              </label>
              <label className="space-y-2 text-sm font-medium">
                DatasetSnapshot
                <select
                  required
                  disabled={loadActive}
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
                        {snapshotLabel(item)}
                      </option>
                    );
                  })}
                </select>
              </label>
            </div>
            {selectedVersion.executionAvailable === false && (
              <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                This StrategyVersion is retained for provenance but cannot
                create a new Experiment.{' '}
                {text(selectedVersion.unavailableReason, '')}
              </p>
            )}
          </fieldset>
          {schema.length > 0 && (
            <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
              <legend className="px-1 text-base font-medium">
                Strategy parameters
              </legend>
              <p className="max-w-2xl text-sm leading-6 text-slate-600">
                Values are captured in this Experiment only. Enter a value
                within the bounds defined by the selected StrategyVersion.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                {schema.map((value) => {
                  const descriptor = object(value);
                  const key = text(descriptor.key, '');
                  const fixed =
                    Number(descriptor.min) === Number(descriptor.max);
                  const error = text(parameterErrors[key], '');
                  return (
                    <label key={key} className="space-y-2 text-sm font-medium">
                      <span className="block">
                        {text(descriptor.label, key)}
                      </span>
                      <input
                        aria-describedby={`${key}-hint ${key}-error`}
                        aria-invalid={Boolean(error)}
                        className={`form-control ${fixed ? 'bg-slate-50 text-slate-600' : ''}`}
                        inputMode={
                          text(descriptor.type) === 'integer'
                            ? 'numeric'
                            : 'decimal'
                        }
                        readOnly={fixed}
                        type="text"
                        value={parameters[key] ?? ''}
                        onChange={(event) => {
                          setParameters((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }));
                          invalidate();
                        }}
                      />
                      <span
                        id={`${key}-hint`}
                        className="block text-xs font-normal text-slate-500"
                      >
                        {fixed
                          ? 'Fixed by methodology.'
                          : `${text(descriptor.type)} · ${text(descriptor.min)} to ${text(descriptor.max)}`}
                        {text(descriptor.description, '')
                          ? ` · ${text(descriptor.description, '')}`
                          : ''}
                      </span>
                      {error && (
                        <span
                          id={`${key}-error`}
                          className="block text-xs font-normal text-red-700"
                        >
                          {error}
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            </fieldset>
          )}
          <fieldset className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
            <legend className="px-1 text-base font-medium">
              Requested period
            </legend>
            <section
              aria-labelledby="available-data-heading"
              className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm"
            >
              <h2 id="available-data-heading" className="font-medium">
                Available data
              </h2>
              <p className="mt-1 text-xs text-slate-600">{proofLine}</p>
              <p className="mt-1 text-xs text-slate-600">
                Policy:{' '}
                {text(
                  selectedSnapshotIntegrity.policyVersion ??
                    selectedSnapshotIntegrity.policy_version ??
                    selectedSnapshotIntegrity.sessionPolicy ??
                    selectedSnapshotIntegrity.session_policy,
                  'ATLAS_HISTORICAL_GAP_POLICY_V1',
                )}
              </p>
              <dl className="mt-3 grid gap-3 sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-slate-500">
                    Earliest native M15
                  </dt>
                  <dd className="font-medium">
                    {snapshots.length
                      ? formatInstant(
                          snapshots.reduce((a, b) =>
                            String(object(a).coverageStart) <
                            String(object(b).coverageStart)
                              ? a
                              : b,
                          ).coverageStart,
                          'UTC',
                        )
                      : 'Unknown'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Latest native M15</dt>
                  <dd className="font-medium">
                    {snapshots.length
                      ? formatInstant(
                          snapshots.reduce((a, b) =>
                            String(object(a).coverageEnd) >
                            String(object(b).coverageEnd)
                              ? a
                              : b,
                          ).coverageEnd,
                          'UTC',
                        )
                      : 'Unknown'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Last snapshot</dt>
                  <dd className="font-medium">
                    {snapshots.length
                      ? snapshotLabel(object(snapshots[snapshots.length - 1]))
                      : 'Unknown'}
                  </dd>
                </div>
              </dl>
              {inventoryLoading && (
                <p className="mt-3 text-xs text-slate-500">
                  Checking selected coverage…
                </p>
              )}
              {inventory &&
                !inventoryLoading &&
                Array.isArray(inventory.blockingReasons) &&
                inventory.blockingReasons.length > 0 &&
                snapshots.length > 0 && (
                  <p className="mt-3 text-xs text-slate-600">
                    Preview:{' '}
                    {inventory.blockingReasons.includes(
                      'INSUFFICIENT_WARMUP',
                    ) ||
                    inventory.blockingReasons.includes('RANGE_OUTSIDE_SNAPSHOT')
                      ? 'This period needs a load first — hit Load below to fetch the missing bars.'
                      : `Preview blocking: ${inventory.blockingReasons.map(String).join(' · ')}`}
                  </p>
                )}
              {inventory &&
                !inventoryLoading &&
                Array.isArray(inventory.blockingReasons) &&
                inventory.blockingReasons.length === 0 &&
                snapshots.length > 0 && (
                  <p className="mt-3 text-xs text-emerald-700">
                    Preview: this period looks ready to validate.
                  </p>
                )}
            </section>
            <div className="grid gap-4 md:grid-cols-2">
              <UtcDateTimePicker
                label="Trading start"
                value={dateInput(start)}
                disabled={loadActive}
                onChange={(value) => {
                  setStart(value);
                  invalidate();
                }}
              />
              <UtcDateTimePicker
                label="Trading end"
                value={dateInput(end)}
                disabled={loadActive}
                onChange={(value) => {
                  setEnd(value);
                  invalidate();
                }}
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-slate-600">
                Presets
              </span>
              {(['1W', '1M', '3M'] as const).map((preset) => (
                <Button
                  key={preset}
                  type="button"
                  className="min-h-8 px-3 text-xs"
                  title={
                    !strategyReady ? 'Pick a StrategyVersion first' : undefined
                  }
                  disabled={!strategyReady || loadActive}
                  onClick={() => applyPreset(preset)}
                >
                  {preset}
                </Button>
              ))}
            </div>
            <div
              className={`rounded-md border p-4 text-sm ${loadRangeTooLarge ? 'border-red-200 bg-red-50 text-red-900' : 'border-slate-200 bg-slate-50 text-slate-700'}`}
            >
              <p className="font-medium">
                Load range{' '}
                <span className="font-normal">[{loadRangeLabel})</span>
              </p>
              <p className="mt-1">
                {loadDurationDays === null
                  ? 'Enter valid UTC times to preview duration.'
                  : `${loadDurationDays.toFixed(1)} days · includes ${Number.isFinite(requiredHistoricalContextBars) ? requiredHistoricalContextBars : 'unknown'} required M15 context bars`}
              </p>
              <p className="mt-1 text-xs">
                Constraints: ≤90 days · ≤40 missing windows (server preflight)
              </p>
              {loadRangeTooLarge && (
                <p className="mt-2 font-medium">
                  Product validation: shorten the period so the
                  required-context-inclusive load range is 90 days or less.
                </p>
              )}
            </div>
            {snapshots.length === 0 && (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                <p className="font-medium">
                  No data yet — load your first month below
                </p>
                <p className="mt-1 text-xs">
                  Pick a period like{' '}
                  <span className="font-mono">2024-01-01 → 2024-02-01 UTC</span>
                  , hit Load, and Atlas will fetch OANDA M1 bars + create a
                  snapshot for you.
                </p>
              </div>
            )}
          </fieldset>
          {/* 3-step directions — makes the month flow impossible to miss */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' : status === 'PENDING' || status === 'RUNNING' ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-700'}`}
              >
                1. Pick dates (UTC)
              </span>
              <span aria-hidden className="text-slate-400">
                →
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' : status === 'PENDING' || status === 'RUNNING' ? 'bg-amber-100 text-amber-800 animate-pulse' : 'bg-slate-100 text-slate-700'}`}
              >
                2. Load missing bars{' '}
                {status === 'PENDING' || status === 'RUNNING'
                  ? `· ${elapsed}s`
                  : ''}
              </span>
              <span aria-hidden className="text-slate-400">
                →
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${coverage?.valid && !loadBlocksCreation ? 'bg-emerald-600 text-white animate-pulse' : 'bg-slate-100 text-slate-700'}`}
              >
                3. Run Experiment
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Load is durable and takes ~30-60s for a month. You can close this
              tab — Atlas keeps the progress. Display timezone only changes
              labels.
            </p>
          </div>
          {status === 'COMPLETED' && (
            <div
              role="status"
              aria-live="polite"
              className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900"
            >
              <p className="font-semibold">
                ✓ Ready — {dateLabel(historicalLoad?.tradingStart, 'UTC')} →{' '}
                {dateLabel(historicalLoad?.tradingEnd, 'UTC')}
              </p>
              <p className="mt-1">
                {text(
                  object(historicalLoad?.snapshot) &&
                    snapshotLabel(object(object(historicalLoad?.snapshot))),
                  text(historicalLoad?.displayLabel, 'Snapshot selected'),
                )}{' '}
                — coverage re-validated. Hit{' '}
                <span className="font-semibold">Run Experiment</span> below.
              </p>
            </div>
          )}
          <section
            aria-live="polite"
            className="rounded-lg border border-blue-200 bg-blue-50 p-5 text-sm text-blue-950"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-medium">Historical data coverage</h2>
                <p className="mt-1">
                  Enter UTC wall-clock times. Display timezone only changes
                  labels, never the request.
                </p>
                {capability?.available === false && (
                  <p className="mt-2 font-medium">
                    Historical loading is unavailable on this server.
                  </p>
                )}
                {historicalLoad && (
                  <>
                    <p className="mt-2 flex flex-wrap items-center gap-2">
                      <span>{text(historicalLoad.displayLabel)}</span>
                      <StatusBadge status={statusOf(historicalLoad.status)} />
                      {(status === 'PENDING' || status === 'RUNNING') && (
                        <span className="inline-flex items-center gap-1 text-xs">
                          <LoaderCircle
                            className="size-3 animate-spin"
                            aria-hidden
                          />{' '}
                          {elapsed}s elapsed
                        </span>
                      )}
                    </p>
                    <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
                      <div>
                        <dt className="text-blue-800/70">Fetched ranges</dt>
                        <dd className="font-medium">
                          {Array.isArray(progress.fetchedRanges)
                            ? progress.fetchedRanges.length
                            : 'Unknown'}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-blue-800/70">Committed ranges</dt>
                        <dd className="font-medium">
                          {Array.isArray(progress.committedRanges)
                            ? progress.committedRanges.length
                            : 'Unknown'}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-blue-800/70">Member minutes</dt>
                        <dd className="font-medium">
                          {text(loadCoverage.memberMinutes, 'Unknown')}
                        </dd>
                      </div>
                    </dl>
                    <p className="mt-2 text-xs">
                      Inserted {text(progress.inserted, 'Unknown')} ·
                      Reactivated {text(progress.reactivated, 'Unknown')} ·
                      Unchanged {text(progress.unchanged, 'Unknown')}
                    </p>
                    {visibleDiagnostics(loadCoverage).length > 0 && (
                      <ul className="mt-2 list-disc pl-5 text-xs">
                        {visibleDiagnostics(loadCoverage).map((item, index) => (
                          <li key={index}>{diagnosticLabel(item)}</li>
                        ))}
                      </ul>
                    )}
                    <p className="mt-2 text-xs font-medium">
                      You can close this tab — load is durable. A month takes
                      ~30-60s (~1 poll/sec).
                    </p>
                    <p className="mt-1 text-xs">
                      Committed progress is saved; Atlas will not restart the
                      command automatically.
                    </p>
                  </>
                )}
                {Boolean(historicalLoad?.failure) && (
                  <p className="mt-1">
                    Load failed. Valid partial bars may remain. Start a new load
                    after reviewing coverage.
                  </p>
                )}
                {pollFailures >= 3 && (
                  <p className="mt-1 font-medium">
                    Status is unknown. Atlas did not resend the load.
                  </p>
                )}
                {Boolean(loadMessage) && (
                  <div className="mt-3">
                    <ErrorPanel error={loadMessage} />
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                {pollFailures >= 3 && (
                  <Button
                    type="button"
                    onClick={() => {
                      setPollFailures(0);
                      setPollPaused(false);
                    }}
                  >
                    Resume status check
                  </Button>
                )}
                <Button
                  type="button"
                  title={
                    !strategyReady ? 'Pick a StrategyVersion first' : undefined
                  }
                  onClick={loadHistoricalData}
                  disabled={
                    !strategyReady ||
                    !start ||
                    !end ||
                    loadRangeTooLarge ||
                    capability?.available === false ||
                    ['PENDING', 'RUNNING'].includes(
                      text(historicalLoad?.status, ''),
                    )
                  }
                >
                  Load missing historical data
                </Button>
              </div>
            </div>
          </section>
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
              Native M15 MID analysis · sparse M1 BID/ASK execution · entry only
              in the immediately following one-minute bucket · Financing
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
                    Validate the selected period to check required historical
                    context and immutable V2 snapshot coverage.
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
                        <dt className="text-slate-600">Historical context</dt>
                        <dd className="font-medium">
                          {text(object(coverage.historicalContext).available)} /{' '}
                          {text(object(coverage.historicalContext).required)}
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
                    {visibleDiagnostics(coverage).length > 0 && (
                      <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-900">
                        {visibleDiagnostics(coverage).map((item, index) => (
                          <li key={index}>{diagnosticLabel(item)}</li>
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
              onClick={() => void validate()}
              disabled={
                validating ||
                !strategy ||
                !snapshot ||
                !start ||
                !end ||
                ['PENDING', 'RUNNING'].includes(
                  text(historicalLoad?.status, ''),
                )
              }
            >
              {validating && (
                <LoaderCircle
                  className="mr-2 size-4 animate-spin"
                  aria-hidden
                />
              )}
              Validate coverage
            </Button>
            <Button
              type="submit"
              title={
                !coverage?.valid
                  ? 'Validate coverage first'
                  : loadBlocksCreation
                    ? 'Historical load must complete successfully first'
                    : undefined
              }
              className={
                coverage?.valid && !loadBlocksCreation && !submitting
                  ? 'animate-pulse shadow-lg'
                  : undefined
              }
              disabled={
                submitting ||
                !coverage?.valid ||
                loadBlocksCreation ||
                selectedVersion.executionAvailable === false ||
                Object.keys(parameterErrors).length > 0
              }
            >
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
      <section className="mx-auto w-full max-w-5xl space-y-8">
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
                Experiment · {dateLabel(data?.createdAt, timeZone)}
              </p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">
                EUR/USD historical simulation
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                {dateLabel(data?.tradingStart, timeZone)} to{' '}
                {dateLabel(data?.tradingEnd, timeZone)}
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
  const { timeZone } = useDisplayTimeZone();
  useEffect(() => {
    let instance: import('lightweight-charts').IChartApi | undefined;
    let observer: ResizeObserver | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({ createChart, CandlestickSeries, LineSeries, ColorType }) => {
        if (
          createChart.length > 0 &&
          typeof navigator !== 'undefined' &&
          navigator.userAgent.includes('jsdom')
        )
          return;
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
          localization: {
            timeFormatter: (time: number) => formatChartTime(time, timeZone),
          },
          timeScale: {
            tickMarkFormatter: (time: number) =>
              formatChartTime(time, timeZone),
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
        candles.setData(strictlyAscending(candleData));
        ema.setData(strictlyAscending(emaData));
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
  }, [chart, levels.entry, levels.exit, levels.stop, levels.target, timeZone]);
  return (
    <div
      ref={ref}
      className="h-[420px] w-full"
      aria-label="Trade candlestick chart with EMA"
    />
  );
}

function pointsRange(
  points: unknown[],
  zone: Parameters<typeof formatInstant>[1],
) {
  if (!points.length) return 'No plotted points.';
  const first = object(points[0]);
  const last = object(points[points.length - 1]);
  return `First point ${dateLabel(first.observed_at, zone)} · Last point ${dateLabel(last.observed_at, zone)}`;
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
  const { timeZone } = useDisplayTimeZone();
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
                {text(summary.direction)} ·{' '}
                {dateLabel(summary.opened_at, timeZone)} →{' '}
                {dateLabel(summary.closed_at, timeZone)}
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
          <p className="mt-1 text-xs text-slate-500">
            Times shown in {timeZone}.
          </p>
          {hasOmitted && (
            <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Chart omits a range from {dateLabel(omitted.start, timeZone)} to{' '}
              {dateLabel(omitted.end, timeZone)} to keep the focused context
              bounded.
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
