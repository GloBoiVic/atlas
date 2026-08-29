'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { AlertCircle, ArrowLeft, LoaderCircle } from 'lucide-react';
import { AppShell } from './app-shell';
import { atlasApi } from '../lib/api-client';
import type { components } from '../lib/api.generated';
import { dateLabel, object, text } from './experiments/shared';
import { formatMetric } from '../lib/experiment-formatters';

type Result = components['schemas']['ExperimentComparisonResponse'];
type ComparisonExperiment = Result['experiments'][number];

const metricLabels: Record<string, string> = {
  netReturn: 'Net Return',
  maxDrawdownPercent: 'Max Drawdown (%)',
  sharpe: 'Sharpe Ratio',
  profitFactor: 'Profit Factor',
  winRate: 'Win Rate',
  expectancy: 'Expectancy',
  tradeCount: 'Trade Count',
};

const configurationLabels: Record<string, string> = {
  strategyVersionId: 'StrategyVersion',
  instrument: 'Instrument',
  datasetSnapshot: 'DatasetSnapshot',
  tradingPeriod: 'Trading period',
  parameters: 'Strategy parameters',
  risk: 'Risk configuration',
  startingCapital: 'Starting capital',
  simulation: 'Simulation assumptions',
  modelVersion: 'Execution model',
  metricContract: 'Metric definitions',
};

const humanize = (value: string) =>
  value
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replaceAll('_', ' ')
    .replace(/^./, (character) => character.toUpperCase());

const showMetric = (value: unknown, key: string) => {
  const metric = object(value);
  if (metric.state === 'INFINITE') return '∞';
  if (metric.state === 'VALUE') {
    const format =
      key === 'netReturn' || key === 'maxDrawdownPercent' || key === 'winRate'
        ? 'percent'
        : key === 'expectancy'
          ? 'money'
          : key === 'profitFactor' || key === 'sharpe'
            ? 'ratio'
            : key === 'tradeCount'
              ? 'integer'
              : 'number';
    return formatMetric(metric, format);
  }
  return metric.state
    ? `${text(metric.state)}${metric.reason ? ` · ${text(metric.reason)}` : ''}`
    : '—';
};

const labelForPath = (path: string) => {
  const [root, ...rest] = path.split('.');
  if (root === 'parameters' && rest.length) {
    return `Parameter · ${rest.map(humanize).join(' · ')}`;
  }
  return configurationLabels[root] ?? humanize(root);
};

const valueForFact = (value: unknown, path: string) => {
  if (value === null || value === undefined || value === '') return '—';
  if (path === 'strategyVersionId') return 'StrategyVersion differs';
  if (path === 'datasetSnapshot') return 'DatasetSnapshot provenance differs';
  if (path === 'instrument')
    return text(object(value).code, 'Instrument differs');
  if (path === 'tradingPeriod') {
    const period = object(value);
    return `${dateLabel(period.start, 'UTC')} → ${dateLabel(period.end, 'UTC')}`;
  }
  if (path === 'startingCapital') {
    const capital = object(value);
    return `${text(capital.value)} ${text(capital.currency, '')}`.trim();
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'string' || typeof value === 'number')
    return String(value);
  if (Array.isArray(value)) return value.map(String).join(', ');
  const entries = Object.entries(object(value)).filter(
    ([key]) =>
      !key.toLowerCase().endsWith('id') &&
      !key.toLowerCase().includes('fingerprint') &&
      !key.toLowerCase().includes('implementation'),
  );
  if (!entries.length) return 'Recorded configuration differs';
  return entries
    .map(
      ([key, item]) =>
        `${humanize(key)}: ${typeof item === 'object' ? 'recorded' : String(item)}`,
    )
    .join(' · ');
};

function IdentityCard({ experiment }: { experiment: ComparisonExperiment }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-atlas-border bg-atlas-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-atlas-foreground-muted">
        Experiment {experiment.slot}
      </p>
      <p className="font-medium">{experiment.label}</p>
      <dl className="flex flex-col gap-2 text-sm">
        <div>
          <dt className="text-xs text-atlas-foreground-muted">
            StrategyVersion
          </dt>
          <dd>
            {text(experiment.strategy.name)} v
            {text(experiment.strategy.version)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-atlas-foreground-muted">Instrument</dt>
          <dd>
            {text(object(experiment.instrument).code, 'Instrument unavailable')}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-atlas-foreground-muted">
            Trading period
          </dt>
          <dd>{valueForFact(experiment.tradingPeriod, 'tradingPeriod')}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
        <Link
          className="text-atlas-primary underline underline-offset-4"
          href={`/experiments/${experiment.id}`}
        >
          Open result
        </Link>
        <Link
          className="text-atlas-primary underline underline-offset-4"
          href={`/experiments/${experiment.id}#trades-heading`}
        >
          Inspect Trades
        </Link>
      </div>
    </div>
  );
}

export function ExperimentComparisonPage() {
  const search = useSearchParams();
  const ids = search.getAll('experimentId');
  const queryKey = ids.join('|');
  const distinct = new Set(ids).size === ids.length;
  const validSelection = ids.length >= 2 && ids.length <= 4 && distinct;
  const [data, setData] = useState<Result | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const requestIds = queryKey ? queryKey.split('|') : [];
    if (!validSelection) return;
    atlasApi
      .compareExperiments(requestIds)
      .then(setData)
      .catch((reason) =>
        setError(
          reason instanceof Error
            ? reason.message
            : 'Atlas could not load this comparison.',
        ),
      );
  }, [queryKey, validSelection]);

  return (
    <AppShell>
      <section
        className="flex flex-col gap-8"
        aria-labelledby="comparison-heading"
      >
        <Link
          href="/experiments"
          className="inline-flex items-center gap-2 text-sm text-atlas-foreground-muted hover:text-atlas-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Experiments
        </Link>
        <header>
          <p className="mb-2 text-sm font-medium text-atlas-primary">
            Transient research view
          </p>
          <h1
            id="comparison-heading"
            className="text-3xl font-semibold tracking-tight"
          >
            Experiment comparison
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
            See what changed and how each completed Experiment performed. Atlas
            preserves the evidence and leaves interpretation to the trader.
          </p>
        </header>
        {!validSelection && (
          <p
            role="alert"
            className="rounded-lg border border-atlas-warning bg-atlas-warning-muted p-4 text-sm text-atlas-warning"
          >
            <AlertCircle className="mr-2 inline size-4" aria-hidden />
            Choose two to four distinct completed Experiments from the
            Experiments list.
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
          >
            <AlertCircle className="mr-2 inline size-4" aria-hidden />
            {error}
          </p>
        )}
        {!data && !error && validSelection && (
          <p className="text-sm text-atlas-foreground-muted">
            <LoaderCircle
              className="mr-2 inline size-4 animate-spin"
              aria-hidden
            />
            Loading comparison…
          </p>
        )}
        {data && (
          <>
            <section aria-labelledby="identity-heading">
              <h2 id="identity-heading" className="text-lg font-semibold">
                Compared Experiments
              </h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {data.experiments.map((experiment) => (
                  <IdentityCard key={experiment.id} experiment={experiment} />
                ))}
              </div>
            </section>
            {data.warnings.length > 0 && (
              <section
                aria-labelledby="warnings-heading"
                className="rounded-lg border border-atlas-warning bg-atlas-warning-muted p-5"
              >
                <h2 id="warnings-heading" className="font-semibold">
                  Comparability warnings
                </h2>
                <p className="mt-1 text-sm text-atlas-warning">
                  Factual differences in the selected inputs and execution
                  context.
                </p>
                <ul className="mt-4 flex flex-col gap-3 text-sm">
                  {data.warnings.map((warning) => (
                    <li key={warning.code}>
                      <strong>{warning.explanation}</strong>
                      <span className="block text-atlas-warning">
                        Affected: {warning.paths.map(labelForPath).join(', ')}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section aria-labelledby="configuration-heading">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2
                  id="configuration-heading"
                  className="text-lg font-semibold"
                >
                  Configuration facts
                </h2>
                <span className="text-sm text-atlas-foreground-muted">
                  Changed facts are shown; unchanged inputs stay out of this
                  table.
                </span>
                {data.strongParameterIsolation && (
                  <span className="text-sm text-atlas-foreground-muted">
                    One parameter differs; other comparison dimensions match.
                  </span>
                )}
              </div>
              <div className="mt-4 overflow-x-auto rounded-lg border border-atlas-border bg-atlas-surface">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="border-b border-atlas-border bg-atlas-surface-hover text-xs text-atlas-foreground-muted">
                    <tr>
                      <th className="px-4 py-3">Changed fact</th>
                      {data.experiments.map((experiment) => (
                        <th key={experiment.id} className="px-4 py-3">
                          Experiment {experiment.slot}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-atlas-border">
                    {data.differences.map((difference) => (
                      <tr key={difference.path}>
                        <th className="px-4 py-3 font-medium">
                          {labelForPath(difference.path)}
                        </th>
                        {data.experiments.map((experiment) => (
                          <td
                            key={experiment.id}
                            className="px-4 py-3 tabular-nums"
                          >
                            {valueForFact(
                              difference.values[experiment.slot],
                              difference.path,
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {data.differences.length === 0 && (
                      <tr>
                        <td
                          colSpan={data.experiments.length + 1}
                          className="px-4 py-5 text-atlas-foreground-muted"
                        >
                          No configuration differences.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
            <section aria-labelledby="metrics-heading">
              <h2 id="metrics-heading" className="text-lg font-semibold">
                Canonical metrics
              </h2>
              <div className="mt-4 overflow-x-auto rounded-lg border border-atlas-border bg-atlas-surface">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead className="border-b border-atlas-border bg-atlas-surface-hover text-xs text-atlas-foreground-muted">
                    <tr>
                      <th className="px-4 py-3">Metric</th>
                      {data.experiments.map((experiment) => (
                        <th key={experiment.id} className="px-4 py-3">
                          Experiment {experiment.slot}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-atlas-border">
                    {Object.entries(metricLabels).map(([key, label]) => (
                      <tr key={key}>
                        <th className="px-4 py-3 font-medium">{label}</th>
                        {data.experiments.map((experiment) => (
                          <td
                            key={experiment.id}
                            className="px-4 py-3 tabular-nums"
                          >
                            {showMetric(experiment.metrics[key], key)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-atlas-foreground-muted">
                Metric states and unavailable reasons are retained from each
                canonical completed-Experiment result.
              </p>
            </section>
          </>
        )}
      </section>
    </AppShell>
  );
}
