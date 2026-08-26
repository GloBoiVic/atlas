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
  marketIdentity,
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

import { MetricSummary as MetricCard } from './metric-summary';
import { EquityChart as Chart } from './equity-charts';
import { PriceChart } from './price-chart';
import { TradesTable } from './trades-table';
import { ErrorPanel } from './load-status';

function pointsRange(
  points: unknown[],
  zone: Parameters<typeof formatInstant>[1],
) {
  if (!points.length) return 'No plotted points.';
  const first = object(points[0]);
  const last = object(points[points.length - 1]);
  return `First point ${dateLabel(first.observed_at, zone)} · Last point ${dateLabel(last.observed_at, zone)}`;
}

function StateDisclosure({ data }: { data: Json }) {
  const { timeZone } = useDisplayTimeZone();
  const config = object(data.simulationConfig);
  const quality = object(data.resultQuality);
  const gaps = Array.isArray(data.gapDecisions) ? data.gapDecisions : [];
  const provenance = object(data.provenance);
  return (
    <div className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-5 text-sm">
      <h2 className="font-medium">Assumptions and provenance</h2>
      <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2">
        <div>
          <dt className="text-atlas-foreground-muted">StrategyVersion</dt>
          <dd className="font-medium">{strategyIdentity(data)}</dd>
        </div>
        <div>
          <dt className="text-atlas-foreground-muted">Instrument / account</dt>
          <dd className="font-medium">
            {marketIdentity(data) || 'Market identity not provided'}
          </dd>
        </div>
        <div>
          <dt className="text-atlas-foreground-muted">Period</dt>
          <dd>
            {dateLabel(data.tradingStart, timeZone)} →{' '}
            {dateLabel(data.tradingEnd, timeZone)}
          </dd>
        </div>
        <div>
          <dt className="text-atlas-foreground-muted">
            Starting capital / Risk
          </dt>
          <dd>
            {text(data.startingCapital)} · {text(data.riskPerTrade)} per Trade
          </dd>
        </div>
        <div>
          <dt className="text-atlas-foreground-muted">Execution</dt>
          <dd>
            Native M15 MID analysis · sparse{' '}
            {text(config.execution_resolution, 'M1')} BID/ASK
            <span className="block text-xs text-atlas-foreground-muted">
              Entry only in the immediately following bucket [frontier, frontier
              + 1 minute)
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-atlas-foreground-muted">Financing</dt>
          <dd className="font-medium">FINANCING EXCLUDED</dd>
        </div>
        <div>
          <dt className="text-atlas-foreground-muted">DatasetSnapshot</dt>
          <dd>
            {text(provenance.snapshotSchema, 'Immutable snapshot')} · immutable
            provenance retained
          </dd>
        </div>
        <div>
          <dt className="text-atlas-foreground-muted">Model</dt>
          <dd>{text(data.modelVersion, 'V2')}</dd>
          <dd className="text-xs text-atlas-foreground-muted">
            Result schema {text(data.resultSchemaVersion, 'V2')}
          </dd>
        </div>
      </dl>
      {Boolean(quality.value) && (
        <p className="mt-5 text-sm text-atlas-foreground-muted">
          Result quality: <strong>{text(quality.value)}</strong>
        </p>
      )}
      {gaps.length > 0 && (
        <div className="mt-4 rounded-md border border-atlas-warning bg-atlas-warning-muted p-3 text-sm text-atlas-warning">
          <strong>Historical data gaps disclosed:</strong> {gaps.length}{' '}
          persisted gap decision{gaps.length === 1 ? '' : 's'}. Missing
          observations are not shown as continuous prices.
        </div>
      )}
      {gaps.length === 0 && Boolean(data.resultQuality) && (
        <p className="mt-4 text-sm text-atlas-foreground-muted">
          No execution gaps affected this result.
        </p>
      )}
      <p className="mt-5 text-xs leading-5 text-atlas-foreground-muted">
        Spread is embedded in BID/ASK execution and is not double-counted. Chart
        sampling, if disclosed above, is presentation-only and never feeds
        metrics.
      </p>
    </div>
  );
}

export function ExperimentResults({ id, data }: { id: string; data: Json }) {
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
            label="Max Drawdown (%)"
            value={metrics.maxDrawdownPercent}
            format="percent"
          />
          <MetricCard label="Sharpe Ratio" value={metrics.sharpe} format="r" />
          <MetricCard
            label="Profit Factor"
            value={metrics.profitFactor}
            format="r"
          />
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
        <div className="rounded-lg border border-atlas-primary bg-atlas-primary-muted p-4 text-sm text-atlas-primary">
          <strong>No Trades</strong> — Strategy produced no executed Trades
          during this period. Return, drawdown, and Trade Count remain valid;
          Trade-dependent metrics are unavailable.
        </div>
      )}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Equity curve</h2>
          <p className="text-sm text-atlas-foreground-muted">
            Full canonical equity history.{' '}
            {text(equity?.samplingPolicy, '') === 'EQUITY_ENVELOPE_V1'
              ? `Displayed envelope sampled from ${text(equity?.sourceCount)} points; omitted ranges are presentation-only.`
              : ''}
          </p>
          <p className="mt-1 text-xs text-atlas-foreground-muted">
            Times shown in {timeZone}. {pointsRange(points, timeZone)}
          </p>
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-3">
          <Chart key="equity" points={points} />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Drawdown</h2>
          <p className="text-sm text-atlas-foreground-muted">
            Amount below the running equity peak. Maximum:{' '}
            {formattedMetric(metrics.maxDrawdownAmount, 'money')} (
            {formattedMetric(metrics.maxDrawdownPercent, 'percent')}),
            explicitly measured from canonical equity.
          </p>
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-3">
          <Chart key="drawdown" points={points} kind="drawdown" />
        </div>
      </section>
      <details className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4">
        <summary className="cursor-pointer font-medium">
          Technical details
        </summary>
        <div className="mt-4">
          <PriceChart id={id} />
        </div>
      </details>
      <section aria-labelledby="trades-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h2 id="trades-heading" className="text-lg font-semibold">
              Trades
            </h2>
            <p className="text-sm text-atlas-foreground-muted">
              Completed Trade episodes, ordered by sequence.
            </p>
          </div>
          {ambiguous > 0 && (
            <p className="text-sm text-atlas-warning">
              {ambiguous} ambiguous · Stop-first policy applied
            </p>
          )}
        </div>
        {error && (
          <ErrorPanel message={error} retry={() => window.location.reload()} />
        )}
        <TradesTable id={id} trades={trades} error={error} />
      </section>
      <details className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4">
        <summary className="cursor-pointer font-medium">
          Assumptions and provenance
        </summary>
        <div className="mt-4">
          <StateDisclosure data={data} />
        </div>
      </details>
    </div>
  );
}
