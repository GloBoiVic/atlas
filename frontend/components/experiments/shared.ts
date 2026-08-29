'use client';
import { ApiError } from '../../lib/api-client';
import {
  formatChartTime,
  formatChartTick,
  formatInstant,
  parseUtcInput,
  utcInputFromInstant,
} from '../../lib/time';
import {
  formatMoney,
  formatPercent,
  formatPrice,
  formatRatio,
} from '../../lib/experiment-formatters';

export type Json = Record<string, unknown>;
export type Status = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
type ChartPoint = { time: import('lightweight-charts').Time };

// Lightweight Charts rejects non-ascending or duplicate timestamps.
export const strictlyAscending = <T extends ChartPoint>(points: T[]): T[] => {
  const sorted = [...points].sort((a, b) => Number(a.time) - Number(b.time));
  return sorted.filter(
    (point, index) =>
      index === 0 || Number(point.time) > Number(sorted[index - 1].time),
  );
};

export const object = (value: unknown): Json =>
  value && typeof value === 'object' ? (value as Json) : {};
export const text = (value: unknown, fallback = '—') =>
  typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : fallback;
export const strategyIdentity = (data: unknown) => {
  const root = object(data);
  const identity = object(root.identity);
  const strategy = object(root.strategy);
  const version = object(identity.strategyVersion ?? root.strategyVersion);
  return text(
    strategy.displayName ?? version.displayName ?? strategy.name,
    'Strategy',
  );
};
export const experimentIdentity = (data: unknown) =>
  firstText([object(data).label], 'Experiment');
const firstText = (values: unknown[], fallback: string) => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value;
  }
  return fallback;
};
export const instrumentIdentity = (data: unknown) => {
  const root = object(data);
  const identity = object(root.identity);
  const instrument = object(
    identity.instrument ??
      root.instrument ??
      root.venueInstrument ??
      object(root.market).instrument,
  );
  return firstText(
    [
      instrument.displayName,
      instrument.code,
      root.instrumentCode,
      root.instrument_code,
    ],
    'Instrument unavailable',
  );
};
export const venueIdentity = (data: unknown) => {
  const root = object(data);
  const identity = object(root.identity);
  const venue = object(
    identity.provider ?? root.venue ?? root.provider ?? root.broker,
  );
  return firstText(
    [
      venue.displayName,
      venue.name,
      venue.code,
      root.providerName,
      root.provider,
    ],
    'Venue unavailable',
  );
};
export const accountIdentity = (data: unknown) => {
  const root = object(data);
  const account = object(root.account ?? root.tradingAccount);
  return firstText(
    [account.displayName, account.name, account.label, root.accountLabel],
    'Account unavailable',
  );
};
export const timeframeIdentity = (data: unknown) => {
  const root = object(data);
  const identity = object(root.identity);
  const analytical = object(identity.analytical);
  const strategy = object(root.strategy);
  return firstText(
    [
      root.timeframe,
      root.strategyTimeframe,
      strategy.timeframe,
      analytical.resolution,
    ],
    'Timeframe unavailable',
  );
};
export const marketIdentity = (data: unknown) =>
  [instrumentIdentity(data), venueIdentity(data), accountIdentity(data)]
    .filter((value) => !value.endsWith(' unavailable'))
    .join(' · ');
export const statusOf = (value: unknown): Status =>
  value === 'RUNNING' || value === 'COMPLETED' || value === 'FAILED'
    ? value
    : 'PENDING';
export const statusLabel = (value: unknown) => statusOf(value);
export const dateLabel = (
  value: unknown,
  zone?: Parameters<typeof formatInstant>[1],
) => formatInstant(value, zone);
export const experimentPeriod = (
  data: unknown,
  zone?: Parameters<typeof formatInstant>[1],
) => {
  const root = object(data);
  const identity = object(root.identity);
  const period = object(identity.tradingPeriod);
  const start = root.tradingStart ?? period.start;
  const end = root.tradingEnd ?? period.end;
  if (start === undefined || end === undefined) return 'Period unavailable';
  return `${dateLabel(start, zone)} → ${dateLabel(end, zone)}`;
};
export const utcDate = (value: string) => {
  const parsed = parseUtcInput(value);
  return parsed ? new Date(parsed) : null;
};
export const quarterHourNow = () => {
  const now = new Date();
  now.setUTCMinutes(Math.floor(now.getUTCMinutes() / 15) * 15, 0, 0);
  return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}T${String(now.getUTCHours()).padStart(2, '0')}:${String(now.getUTCMinutes()).padStart(2, '0')}`;
};
export const snapshotLabel = (item: Json) => {
  const integrity = object(item.integrity);
  const count = Number(
    item.barCount ?? integrity.barCount ?? integrity.bar_count,
  );
  const compact = (value: unknown) =>
    formatInstant(value, 'UTC').replace(/ UTC$/, '');
  const product =
    text(item.snapshotSchema, '') === 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2'
      ? 'native M15 MID + sparse M1 BID/ASK'
      : 'historical data';
  const bars = Number.isFinite(count)
    ? ` · ${count.toLocaleString()} bars`
    : '';
  return `EUR/USD · ${compact(item.coverageStart)} → ${compact(item.coverageEnd)} · ${product}${bars}`;
};
const snapshotFactsKey = (item: Json) => {
  // Use the rendered authoritative facts as the identity key. If two
  // snapshots would look the same to a trader, neither may be selected by
  // guessing which hidden identifier was intended.
  return snapshotLabel(item);
};
export const snapshotOptionState = (item: Json, siblings: Json[]) => {
  const ambiguous =
    siblings.filter(
      (candidate) => snapshotFactsKey(candidate) === snapshotFactsKey(item),
    ).length > 1;
  return {
    label: ambiguous
      ? `${snapshotLabel(item)} · selection unavailable (ambiguous snapshot facts)`
      : snapshotLabel(item),
    disabled: ambiguous,
  };
};
export const diagnosticLabel = (value: unknown) => {
  const item = object(value);
  const components = Array.isArray(item.missing_components)
    ? item.missing_components.map(String).join(', ')
    : '';
  return `${text(item.reason, 'DIAGNOSTIC')} · ${text(item.policy_version, 'policy unknown')}${components ? ` · ${components}` : ''}`;
};
export const formattedMetric = (
  value: unknown,
  format: 'number' | 'percent' | 'money' | 'r' = 'number',
) => {
  const data = metricState(value);
  if (data.state === 'INFINITE') return '∞';
  if (data.state !== 'VALUE') return '—';
  if (format === 'money') return moneyLabel(data.value);
  if (format === 'percent') return percentLabel(data.value);
  if (format === 'r') return rLabel(data.value);
  return text(data.value);
};
export const experimentHeadlineMetrics = (data: unknown) => {
  const metrics = object(object(data).metrics);
  return {
    netReturn: formattedMetric(metrics.netReturn, 'percent'),
    maxDrawdown: formattedMetric(metrics.maxDrawdownPercent, 'percent'),
    sharpe: formattedMetric(metrics.sharpe, 'r'),
    trades: formattedMetric(metrics.tradeCount),
  };
};
export const metricState = (value: unknown) => object(value);
export const priceLabel = (value: unknown) => {
  return formatPrice(value);
};
export const moneyLabel = (value: unknown) => {
  return formatMoney(value);
};
export const rLabel = (value: unknown) => {
  return formatRatio(value);
};
export const percentLabel = (value: unknown) => {
  return formatPercent(value);
};
export const errorMessage = (error: unknown) =>
  typeof error === 'string'
    ? error
    : error instanceof Error
      ? error.message
      : 'Atlas could not complete that request.';

export const productNextAction = (error: ApiError) => {
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

export const scalarFields = (error: unknown) => {
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
export type ParameterValues = Record<string, string>;
export const parameterDefaults = (version: unknown): ParameterValues => {
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

export const iso = (value: string) => parseUtcInput(value);
export const dateInput = (value: string) => utcInputFromInstant(value);
