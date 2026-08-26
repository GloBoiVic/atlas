'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { AlertCircle, ArrowLeft, LoaderCircle } from 'lucide-react';
import { AppShell } from './app-shell';
import { atlasApi } from '../lib/api-client';
import { formatInstant } from '../lib/time';

type Version = {
  id: string;
  displayName: string;
  versionNumber: number;
  implementationKey: string;
  sourceFingerprint: string;
  createdAt: string;
  gitSha: string | null;
  parameterSchema: Record<string, unknown>[];
  timeframe: string;
  requiredHistoricalContextBars: number;
  capabilities: string[];
  experimentCount: number;
  lastUsedAt: string | null;
  executionAvailable: boolean;
  unavailableReason: string | null;
  marketRequirements?: {
    instrument?: string | null;
    resolution?: string | null;
    priceComponent?: string | null;
    requiredHistoricalContextBars?: number | null;
    completedOnly?: boolean | null;
  };
  methodology?: {
    summary?: string | null;
    capabilities?: string[];
  };
};
const date = (v: string | null) => formatInstant(v);

export function StrategiesPage() {
  const [items, setItems] = useState<
    Awaited<ReturnType<typeof atlasApi.listStrategies>>['items']
  >([]);
  const [error, setError] = useState('');
  useEffect(() => {
    atlasApi
      .listStrategies()
      .then((v) => setItems(v.items))
      .catch((e) =>
        setError(
          e instanceof Error ? e.message : 'Atlas could not load Strategies.',
        ),
      );
  }, []);
  return (
    <AppShell>
      <section className="space-y-8" aria-labelledby="strategies-heading">
        <header>
          <p className="mb-2 text-sm font-medium text-atlas-primary">
            Methodology catalog
          </p>
          <h1
            id="strategies-heading"
            className="text-3xl font-semibold tracking-tight"
          >
            Strategies
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
            Inspect immutable StrategyVersions and their local execution
            availability.
          </p>
        </header>
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
          >
            <AlertCircle className="mr-2 inline size-4" />
            {error}
          </p>
        )}
        {!error && !items.length && (
          <p className="rounded-lg border border-atlas-border bg-atlas-surface p-8 text-sm text-atlas-foreground-muted">
            <LoaderCircle className="mr-2 inline size-4 animate-spin" />
            Loading Strategies…
          </p>
        )}
        <div className="overflow-x-auto rounded-lg border border-atlas-border bg-atlas-surface">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-atlas-border bg-atlas-surface-hover text-xs text-atlas-foreground-muted">
              <tr>
                {[
                  'Strategy',
                  'Latest version',
                  'Versions',
                  'Experiments',
                  'Last Experiment',
                ].map((h) => (
                  <th key={h} className="px-4 py-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-atlas-border">
              {items.map((item) => (
                <tr
                  key={item.strategyKey}
                  className="hover:bg-atlas-surface-hover"
                >
                  <td className="px-4 py-4">
                    <Link
                      className="font-medium text-atlas-primary hover:text-atlas-primary-hover hover:underline"
                      href={`/strategies/${item.strategyKey}`}
                    >
                      {item.name}
                    </Link>
                    <span className="block text-xs text-atlas-foreground-muted">
                      {item.description}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    {item.latestVersion?.displayName ?? '—'}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {item.versionCount}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {item.experimentCount}
                  </td>
                  <td className="px-4 py-4 text-atlas-foreground-muted">
                    {date(item.lastExperimentAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}

export function StrategyDetailPage() {
  const { strategyKey } = useParams<{ strategyKey: string }>();
  const [data, setData] = useState<{
    name: string;
    description: string;
    versions: Version[];
  } | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    atlasApi
      .getStrategy(strategyKey)
      .then(setData)
      .catch((e) =>
        setError(
          e instanceof Error
            ? e.message
            : 'Atlas could not load this Strategy.',
        ),
      );
  }, [strategyKey]);
  return (
    <AppShell>
      <section className="max-w-5xl space-y-8">
        <Link
          href="/strategies"
          className="inline-flex items-center gap-2 text-sm text-atlas-foreground-muted hover:text-atlas-foreground"
        >
          <ArrowLeft className="size-4" />
          Strategies
        </Link>
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
          >
            {error}
          </p>
        )}
        {!data && !error && (
          <p className="text-sm text-atlas-foreground-muted">
            Loading Strategy history…
          </p>
        )}
        {data && (
          <>
            <header>
              <p className="mb-2 text-sm font-medium text-atlas-primary">
                Strategy identity
              </p>
              <h1 className="text-3xl font-semibold tracking-tight">
                {data.name}
              </h1>
              <p className="mt-2 text-sm leading-6 text-atlas-foreground-muted">
                {data.description}
              </p>
            </header>
            <div className="space-y-5">
              <h2 className="text-lg font-semibold">Version history</h2>
              {data.versions.map((v) => (
                <article
                  key={v.id}
                  className="rounded-lg border border-atlas-border bg-atlas-surface p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold">{v.displayName}</h3>
                      <p className="mt-1 text-sm text-atlas-foreground-muted">
                        {v.implementationKey} · created {date(v.createdAt)}
                      </p>
                    </div>
                    <span
                      className={`status rounded-full border px-2.5 py-1 ${v.executionAvailable ? 'border-atlas-positive bg-atlas-positive-muted text-atlas-positive' : 'border-atlas-warning bg-atlas-warning-muted text-atlas-warning'}`}
                    >
                      {v.executionAvailable
                        ? 'Available locally'
                        : 'Unavailable locally'}
                    </span>
                  </div>
                  <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                      <dt className="text-atlas-foreground-muted">
                        Experiments
                      </dt>
                      <dd className="font-medium">{v.experimentCount}</dd>
                    </div>
                    <div>
                      <dt className="text-atlas-foreground-muted">
                        Market requirements
                      </dt>
                      <dd className="font-medium">
                        {v.marketRequirements?.instrument ??
                          'Instrument unavailable'}{' '}
                        · {v.marketRequirements?.resolution ?? v.timeframe} ·{' '}
                        {v.marketRequirements?.priceComponent ??
                          'Price basis unavailable'}
                      </dd>
                      <dd className="text-xs text-atlas-foreground-muted">
                        {v.marketRequirements?.requiredHistoricalContextBars ??
                          v.requiredHistoricalContextBars}{' '}
                        required historical bars
                      </dd>
                    </div>
                    <div>
                      <dt className="text-atlas-foreground-muted">
                        Methodology
                      </dt>
                      <dd className="font-medium">
                        {v.methodology?.summary ?? 'Methodology unavailable'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-atlas-foreground-muted">Last used</dt>
                      <dd className="font-medium">{date(v.lastUsedAt)}</dd>
                    </div>
                  </dl>
                  <div className="mt-5">
                    <p className="text-sm font-medium">Strategy settings</p>
                    <ul className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
                      {v.parameterSchema.map((p) => (
                        <li
                          key={String(p.key)}
                          className="rounded-md bg-atlas-surface-hover px-3 py-2"
                        >
                          <span className="font-medium">
                            {String(p.label ?? p.key)}
                          </span>
                          <span className="ml-2 text-atlas-foreground-muted">
                            default {String(p.default ?? '—')}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <details className="mt-5 border-t border-atlas-border pt-4">
                    <summary className="cursor-pointer text-sm font-medium">
                      Technical details
                    </summary>
                    <div className="mt-3 space-y-2">
                      <p className="break-all font-mono text-xs text-atlas-foreground-muted">
                        StrategyVersion fingerprint: {v.sourceFingerprint}
                      </p>
                      {v.gitSha && (
                        <p className="font-mono text-xs text-atlas-foreground-muted">
                          Git SHA: {v.gitSha}
                        </p>
                      )}
                      <p className="text-xs text-atlas-foreground-muted">
                        Immutable parameter schema retained for reproducibility.
                      </p>
                    </div>
                  </details>
                  {!v.executionAvailable && (
                    <p className="mt-4 rounded-md border border-atlas-warning bg-atlas-warning-muted p-3 text-sm text-atlas-warning">
                      Retained for provenance; new Experiments are blocked.{' '}
                      {v.unavailableReason}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </>
        )}
      </section>
    </AppShell>
  );
}
