'use client';

import { useCallback } from 'react';
import { atlasApi } from '../lib/api-client';
import { formatInstrumentDisplay } from '../lib/instrument';
import { formatInstant } from '../lib/time';
import { useDisplayTimeZone } from '../app/providers';
import { PaperBrokerStateSection } from './paper-broker-state';
import { PaperTradeHistory } from './paper-trade-history';
import {
  EmptyState,
  LoadingState,
  ReadError,
  UnavailableState,
  useReadResource,
} from './read-resource';
import type { components } from '../lib/api.generated';

type PaperCapability = components['schemas']['PaperCapabilityResponse'];
type PaperStatus = components['schemas']['PaperRuntimeStatusResponse'];

const display = (value: string | number | boolean | null | undefined) =>
  value === null || value === undefined || value === '' ? '—' : String(value);

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-atlas-border pt-3">
      <dt className="text-xs text-atlas-foreground-muted">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{value}</dd>
    </div>
  );
}

export function PaperCapabilitySection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const loader = useCallback(() => atlasApi.paperCapability(), []);
  const { state, retry } = useReadResource<PaperCapability>(loader);

  return (
    <section
      aria-labelledby="paper-capability-heading"
      className={compact ? 'space-y-4' : 'space-y-4'}
    >
      <div>
        <h2 id="paper-capability-heading" className="text-lg font-semibold">
          PAPER capability
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Provider facts describe what the configured PAPER boundary can report.
        </p>
      </div>
      {state.status === 'loading' && <LoadingState label="PAPER capability" />}
      {state.status === 'error' && (
        <ReadError error={state.error} retry={retry} />
      )}
      {state.status === 'ready' && (
        <div className="space-y-4">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <Fact label="Provider" value={state.data.provider} />
            <Fact label="Environment" value={state.data.environment} />
            <Fact
              label="Instrument"
              value={formatInstrumentDisplay(state.data.instrument)}
            />
            <Fact
              label="Availability"
              value={state.data.available ? 'Available' : 'Unavailable'}
            />
          </dl>
          {state.data.available ? (
            <p className="text-sm text-atlas-positive" role="status">
              PAPER capability is available for the configured market boundary.
            </p>
          ) : (
            <UnavailableState>
              PAPER capability is unavailable. Reason:{' '}
              {display(state.data.reasonCode) === '—'
                ? 'No reason code returned.'
                : state.data.reasonCode}
            </UnavailableState>
          )}
        </div>
      )}
    </section>
  );
}

function PaperStatusFacts({ data }: { data: PaperStatus }) {
  const { timeZone } = useDisplayTimeZone();
  const activation = data.activation;
  return (
    <div className="space-y-4">
      <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        <Fact label="Lifecycle state" value={activation.lifecycleState} />
        <Fact label="Operational phase" value={activation.operationalPhase} />
        <Fact
          label="Current financial position state"
          value={display(data.currentFinancialPositionState)}
        />
        <Fact
          label="Execution outcome"
          value={display(data.executionOutcome)}
        />
        <Fact label="Reconciliation status" value={data.reconciliationStatus} />
        <Fact
          label="State changed"
          value={formatInstant(activation.stateChangedAt, timeZone)}
        />
      </dl>
      {activation.stateReasonCode && (
        <p className="text-sm text-atlas-foreground-muted">
          State reason:{' '}
          <span className="font-mono">{activation.stateReasonCode}</span>
        </p>
      )}
      {activation.stateDetail && (
        <p className="text-sm text-atlas-foreground-muted">
          {activation.stateDetail}
        </p>
      )}
      {data.terminalRuntimeStateDoesNotProveFlat && (
        <p
          role="alert"
          className="border-l-2 border-atlas-warning bg-atlas-warning-muted p-3 text-sm text-atlas-warning"
        >
          Terminal runtime state does not prove broker flatness.
        </p>
      )}
    </div>
  );
}

function CompactPaperStatus({ data }: { data: PaperStatus }) {
  return (
    <div className="space-y-3">
      <p className="status status-success">Active</p>
      <p className="text-sm text-atlas-foreground-muted">
        Phase{' '}
        <span className="font-mono">{data.activation.operationalPhase}</span>
      </p>
    </div>
  );
}

export function PaperActiveStatusSection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const loader = useCallback(() => atlasApi.activePaperStatus(), []);
  const { state, retry } = useReadResource<PaperStatus | null>(loader);

  return (
    <section
      aria-labelledby="paper-current-status-heading"
      className={compact ? 'space-y-4' : 'space-y-4'}
    >
      <div>
        <h2 id="paper-current-status-heading" className="text-lg font-semibold">
          {compact ? 'Runtime' : 'Runtime status'}
        </h2>
        {!compact && (
          <p className="mt-1 text-sm text-atlas-foreground-muted">
            Runtime is Atlas activation state, not broker exposure. This is a
            current-state read, not a session history.
          </p>
        )}
      </div>
      {state.status === 'loading' && (
        <LoadingState label={compact ? 'runtime' : 'Runtime status'} />
      )}
      {state.status === 'error' &&
        (compact ? (
          <div className="space-y-3">
            <UnavailableState>Runtime unavailable</UnavailableState>
            <button
              type="button"
              onClick={retry}
              className="text-sm font-medium text-atlas-primary underline-offset-2 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : (
          <ReadError error={state.error} retry={retry} />
        ))}
      {state.status === 'ready' &&
        (state.data === null ? (
          compact ? (
            <EmptyState>No active runtime</EmptyState>
          ) : (
            <EmptyState>
              No active PAPER activation reported. Current-state result:{' '}
              <span className="font-mono">PAPER_ACTIVATION_NOT_ACTIVE</span>
            </EmptyState>
          )
        ) : compact ? (
          <CompactPaperStatus data={state.data} />
        ) : (
          <PaperStatusFacts data={state.data} />
        ))}
    </section>
  );
}

export function PaperStatus() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
      <header className="max-w-3xl">
        <p className="mb-2 text-sm font-medium text-atlas-primary">
          Read-only PAPER status
        </p>
        <h1
          id="paper-heading"
          className="text-3xl font-semibold tracking-tight"
        >
          PAPER
        </h1>
        <p className="mt-3 text-sm leading-6 text-atlas-foreground-muted">
          Current PAPER capability, broker exposure, and runtime status are
          observable here, but this surface does not control the runtime or
          broker.
        </p>
      </header>
      <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
        <PaperBrokerStateSection />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6 rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <PaperCapabilitySection />
        </div>
        <div className="space-y-6 rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <PaperActiveStatusSection />
        </div>
      </div>
      <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5">
        <PaperTradeHistory limit={20} />
      </div>
      <aside
        aria-labelledby="paper-safety-heading"
        className="border-l-2 border-atlas-warning bg-atlas-warning-muted p-5"
      >
        <h2 id="paper-safety-heading" className="font-semibold">
          PAPER evidence boundary
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-atlas-warning">
          This surface does not reconstruct historical activations. It does not
          prove broker flatness. It shows only the current capability and status
          facts returned by the read API.
        </p>
      </aside>
    </div>
  );
}
