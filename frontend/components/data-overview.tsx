'use client';

import { useCallback } from 'react';
import { atlasApi } from '../lib/api-client';
import { formatInstant } from '../lib/time';
import { useDisplayTimeZone } from '../app/providers';
import type { components } from '../lib/api.generated';
import {
  EmptyState,
  LoadingState,
  ReadError,
  UnavailableState,
  useReadResource,
} from './read-resource';

type HistoricalCapability =
  components['schemas']['HistoricalDataCapabilityResponse'];
type ConfigurationOptions =
  components['schemas']['ExperimentConfigurationOptionsResponse'];
type HistoricalLoad = components['schemas']['HistoricalDataLoadStatusResponse'];
type Snapshot = ConfigurationOptions['datasetSnapshots'][number];

const display = (value: unknown) =>
  value === null || value === undefined || value === '' ? '—' : String(value);

const readableKey = (key: string) =>
  key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/^./, (value) => value.toUpperCase());

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-t border-atlas-border pt-3">
      <dt className="text-xs text-atlas-foreground-muted">{label}</dt>
      <dd className="mt-1 break-all text-sm font-medium">{value}</dd>
    </div>
  );
}

function ProductFact({ product }: { product: Record<string, unknown> }) {
  const components = Array.isArray(product.components)
    ? product.components.map(String).join(', ')
    : display(product.components);
  return (
    <li className="border-t border-atlas-border pt-3 text-sm">
      <span className="font-medium">{display(product.product)}</span>
      <span className="text-atlas-foreground-muted">
        {' · '}
        {display(product.resolution)} · {components}
      </span>
    </li>
  );
}

export function HistoricalCapabilitySection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const loader = useCallback(() => atlasApi.historicalCapability(), []);
  const { state, retry } = useReadResource<HistoricalCapability>(loader);

  return (
    <section
      aria-labelledby="historical-capability-heading"
      className={compact ? 'space-y-4' : 'space-y-4'}
    >
      <div>
        <h2
          id="historical-capability-heading"
          className="text-lg font-semibold"
        >
          Historical data capability
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Provider and product facts from the historical-data boundary.
        </p>
      </div>
      {state.status === 'loading' && (
        <LoadingState label="historical data capability" />
      )}
      {state.status === 'error' && (
        <ReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && (
        <div className="space-y-4">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <Fact label="Provider" value={state.data.provider} />
            <Fact label="Instrument" value={state.data.instrument} />
            <Fact
              label="Availability"
              value={state.data.available ? 'Available' : 'Unavailable'}
            />
            <Fact label="Reason code" value={display(state.data.reasonCode)} />
          </dl>
          {state.data.products.length === 0 ? (
            <EmptyState>No historical products were returned.</EmptyState>
          ) : (
            <div>
              <h3 className="text-sm font-medium">Available products</h3>
              <ul className="mt-2 grid gap-3 sm:grid-cols-2">
                {state.data.products.map((product, index) => (
                  <ProductFact
                    key={`${display(product.product)}-${index}`}
                    product={product}
                  />
                ))}
              </ul>
            </div>
          )}
          {!state.data.available && (
            <UnavailableState>
              Historical market data is unavailable for this environment.
            </UnavailableState>
          )}
        </div>
      )}
    </section>
  );
}

function integrityValue(value: unknown) {
  if (Array.isArray(value)) return value.map(String).join(', ');
  if (value && typeof value === 'object') return JSON.stringify(value);
  return display(value);
}

function SnapshotCard({ snapshot }: { snapshot: Snapshot }) {
  const { timeZone } = useDisplayTimeZone();
  return (
    <article className="min-w-0 border-t border-atlas-border pt-4">
      <h3 className="break-all text-sm font-semibold">DatasetSnapshot</h3>
      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
        <Fact label="Fingerprint" value={snapshot.fingerprint} />
        <Fact label="Schema" value={snapshot.snapshotSchema} />
        <Fact
          label="Coverage start"
          value={formatInstant(snapshot.coverageStart, timeZone)}
        />
        <Fact
          label="Coverage end"
          value={formatInstant(snapshot.coverageEnd, timeZone)}
        />
      </dl>
      {Object.keys(snapshot.integrity).length > 0 && (
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          {Object.entries(snapshot.integrity).map(([key, value]) => (
            <div key={key} className="min-w-0 break-words">
              <dt className="inline text-atlas-foreground-muted">
                {readableKey(key)}:{' '}
              </dt>
              <dd className="inline break-all">{integrityValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

export function SnapshotOptionsSection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const loader = useCallback(() => atlasApi.configurationOptions(), []);
  const { state, retry } = useReadResource<ConfigurationOptions>(loader);

  return (
    <section
      aria-labelledby="dataset-snapshots-heading"
      className={compact ? 'space-y-4' : 'space-y-4'}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 id="dataset-snapshots-heading" className="text-lg font-semibold">
            Available DatasetSnapshots
          </h2>
          <p className="mt-1 text-sm text-atlas-foreground-muted">
            Immutable options currently returned by Experiment configuration.
          </p>
        </div>
        {state.status === 'ready' && (
          <span className="text-sm tabular-nums text-atlas-foreground-muted">
            {state.data.datasetSnapshots.length} returned options
          </span>
        )}
      </div>
      {state.status === 'loading' && <LoadingState label="DatasetSnapshots" />}
      {state.status === 'error' && (
        <ReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' &&
        (state.data.datasetSnapshots.length === 0 ? (
          <EmptyState>
            No DatasetSnapshots are available in configuration options.
          </EmptyState>
        ) : (
          <div className="grid gap-5 md:grid-cols-2">
            {state.data.datasetSnapshots.map((snapshot) => (
              <SnapshotCard key={snapshot.id} snapshot={snapshot} />
            ))}
          </div>
        ))}
    </section>
  );
}

function loadPeriod(load: HistoricalLoad) {
  return load.requestedPeriod;
}

export function ActiveHistoricalLoadSection() {
  const loader = useCallback(() => atlasApi.activeHistoricalLoad(), []);
  const { state, retry } = useReadResource<HistoricalLoad | null>(loader);
  const { timeZone } = useDisplayTimeZone();

  return (
    <section aria-labelledby="historical-load-heading" className="space-y-4">
      <div>
        <h2 id="historical-load-heading" className="text-lg font-semibold">
          Current historical load
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Read-only status for an active load request, when one is reported.
        </p>
      </div>
      {state.status === 'loading' && (
        <LoadingState label="current historical load" />
      )}
      {state.status === 'error' && (
        <ReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' &&
        (state.data === null ? (
          <EmptyState>No historical load is active.</EmptyState>
        ) : (
          <div className="space-y-4">
            <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              <Fact label="Status" value={state.data.status} />
              <Fact label="Request" value={state.data.displayLabel} />
              <Fact
                label="Created"
                value={formatInstant(state.data.createdAt, timeZone)}
              />
              <Fact
                label="Started"
                value={formatInstant(state.data.startedAt, timeZone)}
              />
              <Fact
                label="Finished"
                value={formatInstant(state.data.finishedAt, timeZone)}
              />
            </dl>
            <p className="text-sm text-atlas-foreground-muted">
              Requested period:{' '}
              {formatInstant(loadPeriod(state.data).start, timeZone)} →{' '}
              {formatInstant(loadPeriod(state.data).end, timeZone)}
            </p>
          </div>
        ))}
    </section>
  );
}

export function DataOverview() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
      <header className="max-w-3xl">
        <p className="mb-2 text-sm font-medium text-atlas-primary">
          Historical market data
        </p>
        <h1 id="data-heading" className="text-3xl font-semibold tracking-tight">
          Data
        </h1>
        <p className="mt-3 text-sm leading-6 text-atlas-foreground-muted">
          Inspect historical capability, immutable DatasetSnapshot options, and
          the current load status without changing data.
        </p>
      </header>
      <div className="space-y-6">
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <HistoricalCapabilitySection />
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <SnapshotOptionsSection />
        </div>
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <ActiveHistoricalLoadSection />
        </div>
      </div>
    </div>
  );
}
