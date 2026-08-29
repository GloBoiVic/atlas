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
import { TradePriceChart as TradeChart } from './price-chart';
import { Lineage } from './lineage';
import { ErrorPanel } from './load-status';

export function TradeDetailPage() {
  const params = useParams<{ experimentId: string; sequenceNumber: string }>();
  const [data, setData] = useState<Json | null>(null);
  const [experiment, setExperiment] = useState<Json | null>(null);
  const [error, setError] = useState('');
  const sequence = Number(params.sequenceNumber);
  const { timeZone } = useDisplayTimeZone();
  const invalidSequence = !Number.isInteger(sequence) || sequence < 1;
  useEffect(() => {
    if (invalidSequence) return;
    Promise.all([
      atlasApi.getTrade(params.experimentId, sequence),
      atlasApi.getExperiment(params.experimentId),
    ])
      .then(([trade, owner]) => {
        setData(object(trade));
        setExperiment(object(owner));
      })
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
        <p className="text-sm text-atlas-foreground-muted">
          <LoaderCircle
            className="mr-2 inline size-4 animate-spin"
            aria-hidden
          />
          Loading Trade…
        </p>
      </AppShell>
    );
  const summary = object(data.summary);
  const owner = experiment ?? data;
  const chart = object(data.chart);
  const entryPolicy = object(data.entryPolicy);
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
            className="mb-5 inline-flex items-center gap-2 text-sm text-atlas-foreground-muted hover:text-atlas-foreground"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Back to Experiment
          </Link>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-atlas-foreground-muted">
                {marketIdentity(owner) ? `${marketIdentity(owner)} · ` : ''}
                {strategyIdentity(owner)}
              </p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">
                Trade {text(summary.sequence_number)} ·{' '}
                {text(summary.direction).toLowerCase()}
              </h1>
              <p className="mt-2 text-sm text-atlas-foreground-muted">
                {text(summary.direction)} ·{' '}
                {dateLabel(summary.opened_at, timeZone)} →{' '}
                {dateLabel(summary.closed_at, timeZone)}
              </p>
            </div>
            <span className="status rounded-full border border-atlas-border bg-atlas-surface px-2.5 py-1 text-atlas-foreground-muted">
              Historical Experiment
            </span>
          </div>
        </header>
        <Lineage
          data={data}
          context={
            <section className="mt-6 border-t border-atlas-border pt-5">
              <h3 className="text-sm font-medium">Trade context</h3>
              <p className="mt-1 text-sm text-atlas-foreground-muted">
                Persisted analytical candles, EMA series, and setup markers from
                the immutable DatasetSnapshot. Atlas supplied the evidence; the
                browser does not infer Strategy identity.
              </p>
              <p className="mt-1 text-xs text-atlas-foreground-muted">
                Times shown in {timeZone}.
              </p>
              {hasOmitted && (
                <p className="mt-3 rounded-md border border-atlas-warning bg-atlas-warning-muted p-3 text-sm text-atlas-warning">
                  Chart omits a range from {dateLabel(omitted.start, timeZone)}{' '}
                  to {dateLabel(omitted.end, timeZone)} to keep the focused
                  context bounded.
                </p>
              )}
              <div className="mt-4 rounded-lg border border-atlas-border bg-atlas-surface p-3">
                <TradeChart chart={chart} levels={levels} />
              </div>
            </section>
          }
        />
        <section className="border-y border-atlas-border py-5">
          <h2 className="text-lg font-semibold">Protection</h2>
          <p className="mt-1 max-w-2xl text-sm text-atlas-foreground-muted">
            Stop and target levels recorded by the Risk decision for this Trade.
          </p>
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs text-atlas-foreground-muted">
                Entry policy
              </dt>
              <dd>{text(entryPolicy.entryPolicy, 'Not recorded')}</dd>
            </div>
            <div>
              <dt className="text-xs text-atlas-foreground-muted">Trigger</dt>
              <dd className="tabular-nums">
                {priceLabel(entryPolicy.triggerPrice)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-atlas-foreground-muted">
                Initial stop
              </dt>
              <dd className="tabular-nums">{priceLabel(data.initial_stop)}</dd>
            </div>
            <div>
              <dt className="text-xs text-atlas-foreground-muted">Target</dt>
              <dd className="tabular-nums">{priceLabel(data.target)}</dd>
            </div>
          </dl>
        </section>
        <section aria-labelledby="outcome-heading">
          <h2 id="outcome-heading" className="text-lg font-semibold">
            Outcome
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-atlas-foreground-muted">
            Persisted result facts for this completed Trade.
          </p>
          <dl className="mt-4 grid gap-x-6 gap-y-5 border-y border-atlas-border py-5 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Net P&L"
              value={{ state: 'VALUE', value: text(summary.net_pnl) }}
              format="money"
            />
            <MetricCard
              label="R multiple"
              value={{ state: 'VALUE', value: text(summary.r_multiple) }}
              format="r"
            />
            <div>
              <dt className="text-xs text-atlas-foreground-muted">
                Entry / exit
              </dt>
              <dd className="mt-1 tabular-nums">
                {priceLabel(summary.entry_price)} →{' '}
                {priceLabel(summary.exit_price)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-atlas-foreground-muted">
                Exit reason
              </dt>
              <dd className="mt-1">{text(summary.exit_reason)}</dd>
            </div>
            <div>
              <dt className="text-xs text-atlas-foreground-muted">
                Initial stop / target
              </dt>
              <dd className="mt-1 tabular-nums">
                {priceLabel(data.initial_stop)} / {priceLabel(data.target)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-atlas-foreground-muted">Ambiguity</dt>
              <dd className="mt-1">
                {ambiguous
                  ? 'Ambiguous intrabar resolution — Stop-first policy applied.'
                  : 'None recorded'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-atlas-foreground-muted">Financing</dt>
              <dd className="mt-1 font-medium">
                {text(data.financing_disclosure)}
              </dd>
            </div>
          </dl>
        </section>
        <details className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4">
          <summary className="cursor-pointer font-medium">
            Technical details
          </summary>
          <div className="mt-5 space-y-6">
            {data.entryPolicy || data.proposalStatus || data.setupFacts ? (
              <section>
                <h3 className="text-sm font-medium">Execution evidence</h3>
                <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <dt className="text-xs text-atlas-foreground-muted">
                      Entry policy
                    </dt>
                    <dd>{text(entryPolicy.entryPolicy, '—')}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-atlas-foreground-muted">
                      Proposal status
                    </dt>
                    <dd>{text(entryPolicy.proposalStatus)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-atlas-foreground-muted">
                      Expiry
                    </dt>
                    <dd>{dateLabel(entryPolicy.expiry, timeZone)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-atlas-foreground-muted">
                      Model
                    </dt>
                    <dd className="font-mono text-xs">
                      {text(data.model_version, 'Historical execution')}
                    </dd>
                  </div>
                </dl>
              </section>
            ) : null}
          </div>
        </details>
      </section>
    </AppShell>
  );
}
