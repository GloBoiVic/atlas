'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { AlertCircle, ArrowLeft, LoaderCircle } from 'lucide-react';
import { AppShell } from './app-shell';
import { atlasApi } from '../lib/api-client';
import type { components } from '../lib/api.generated';

type Result = components['schemas']['ExperimentComparisonResponse'];
const show = (v: unknown) =>
  v === null || v === undefined
    ? '—'
    : typeof v === 'object'
      ? JSON.stringify(v)
      : String(v);
const metric = (v: unknown) => {
  const x = v as
    { state?: string; value?: unknown; reason?: unknown } | undefined;
  return x?.state === 'INFINITE'
    ? '∞'
    : x?.state === 'VALUE'
      ? show(x.value)
      : x?.state
        ? `${x.state}${x.reason ? ` · ${show(x.reason)}` : ''}`
        : '—';
};
const field = (path: string) =>
  path
    .split('.')
    .map((part) => part.replace(/([A-Z])/g, ' $1'))
    .join(' · ');

export function ExperimentComparisonPage() {
  const search = useSearchParams();
  const ids = search.getAll('experimentId');
  const queryKey = ids.join('|');
  const [data, setData] = useState<Result | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const requestIds = queryKey ? queryKey.split('|') : [];
    if (requestIds.length < 2 || requestIds.length > 4) return;
    atlasApi
      .compareExperiments(requestIds)
      .then(setData)
      .catch((e) =>
        setError(
          e instanceof Error
            ? e.message
            : 'Atlas could not load this comparison.',
        ),
      );
  }, [queryKey]);
  return (
    <AppShell>
      <section className="space-y-8" aria-labelledby="comparison-heading">
        <Link
          href="/experiments"
          className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-950"
        >
          <ArrowLeft className="size-4" />
          Experiments
        </Link>
        <header>
          <p className="mb-2 text-sm font-medium text-blue-700">
            Transient research view
          </p>
          <h1
            id="comparison-heading"
            className="text-3xl font-semibold tracking-tight"
          >
            Experiment comparison
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Review immutable configuration facts side by side. This view does
            not rank Experiments or recommend a choice.
          </p>
        </header>
        {(ids.length < 2 || ids.length > 4) && (
          <p
            role="alert"
            className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
          >
            <AlertCircle className="mr-2 inline size-4" />
            Choose two to four distinct completed Experiments from the
            Experiments list.
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900"
          >
            <AlertCircle className="mr-2 inline size-4" />
            {error}
          </p>
        )}
        {!data && !error && ids.length >= 2 && ids.length <= 4 && (
          <p className="text-sm text-slate-600">
            <LoaderCircle className="mr-2 inline size-4 animate-spin" />
            Loading comparison…
          </p>
        )}
        {data && (
          <>
            <section aria-labelledby="identity-heading">
              <h2 id="identity-heading" className="text-lg font-semibold">
                Experiments
              </h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {data.experiments.map((x) => (
                  <Link
                    key={x.id}
                    href={`/experiments/${x.id}`}
                    className="rounded-lg border border-slate-200 bg-white p-4 hover:border-slate-400"
                  >
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Experiment {x.slot}
                    </p>
                    <p className="mt-2 font-medium">{x.label}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      {show(x.strategy.name)} · v{show(x.strategy.version)}
                    </p>
                  </Link>
                ))}
              </div>
            </section>
            {data.warnings.length > 0 && (
              <section
                aria-labelledby="warnings-heading"
                className="rounded-lg border border-amber-200 bg-amber-50 p-5"
              >
                <h2 id="warnings-heading" className="font-semibold">
                  Comparability warnings
                </h2>
                <p className="mt-1 text-sm text-amber-900">
                  These are factual differences in the selected inputs and
                  execution context.
                </p>
                <ul className="mt-4 space-y-3 text-sm">
                  {data.warnings.map((w) => (
                    <li key={w.code}>
                      <strong>{w.explanation}</strong>
                      <span className="block text-amber-800">
                        Affected: {w.paths.join(', ')}
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
                {data.strongParameterIsolation && (
                  <span className="text-sm text-slate-600">
                    One parameter differs; other comparison dimensions match.
                  </span>
                )}
              </div>
              <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-600">
                    <tr>
                      <th className="px-4 py-3">Fact</th>
                      {data.experiments.map((x) => (
                        <th key={x.id} className="px-4 py-3">
                          Experiment {x.slot}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.differences.map((d) => (
                      <tr key={d.path}>
                        <th className="px-4 py-3 font-medium">
                          {field(d.path)}
                        </th>
                        {data.experiments.map((x) => (
                          <td
                            key={x.id}
                            className="px-4 py-3 font-mono text-xs"
                          >
                            {show(d.values[x.slot])}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {data.differences.length === 0 && (
                      <tr>
                        <td
                          colSpan={data.experiments.length + 1}
                          className="px-4 py-5 text-slate-600"
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
              <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-600">
                    <tr>
                      <th className="px-4 py-3">Metric</th>
                      {data.experiments.map((x) => (
                        <th key={x.id} className="px-4 py-3">
                          Experiment {x.slot}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {[
                      'netReturn',
                      'maxDrawdownPercent',
                      'sharpe',
                      'profitFactor',
                      'winRate',
                      'expectancy',
                      'tradeCount',
                    ].map((key) => (
                      <tr key={key}>
                        <th className="px-4 py-3 font-medium">{field(key)}</th>
                        {data.experiments.map((x) => (
                          <td key={x.id} className="px-4 py-3 tabular-nums">
                            {metric(x.metrics[key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-slate-500">
                Metric states and unavailable reasons are retained from the
                canonical completed-Experiment result.
              </p>
            </section>
            <div className="flex flex-wrap gap-4 text-sm">
              {data.experiments.map((x) => (
                <Link
                  key={x.id}
                  className="text-blue-700 underline underline-offset-4"
                  href={`/experiments/${x.id}`}
                >
                  Open {x.slot} result and Trades
                </Link>
              ))}
            </div>
          </>
        )}
      </section>
    </AppShell>
  );
}
