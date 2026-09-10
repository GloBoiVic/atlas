'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { atlasApi, ApiError } from '../lib/api-client';
import { formatInstrumentDisplay } from '../lib/instrument';
import { formatInstant } from '../lib/time';
import {
  formatPaperLifecycle,
  formatPaperOperationalPhase,
  PAPER_STOP_REASON,
} from '../lib/paper-control';
import { useDisplayTimeZone } from '../app/providers';
import { PaperBrokerStateSection } from './paper-broker-state';
import { PaperTradeHistory } from './paper-trade-history';
import {
  EmptyState,
  LoadingState,
  ReadError,
  UnavailableState,
  type ReadState,
  useReadResource,
} from './read-resource';
import type { components } from '../lib/api.generated';

type PaperCapability = components['schemas']['PaperCapabilityResponse'];
type PaperStatus = components['schemas']['PaperRuntimeStatusResponse'];

const PAPER_STATUS_POLL_MS = 3000;
const TERMINAL_LIFECYCLE_STATES = new Set(['STOPPED', 'BLOCKED', 'FAILED']);

const display = (value: string | number | boolean | null | undefined) =>
  value === null || value === undefined || value === '' ? '—' : String(value);

const isTerminalLifecycle = (value: string) =>
  TERMINAL_LIFECYCLE_STATES.has(value);

function formatRiskPercentage(value: string | undefined): string {
  if (!value) return 'Unavailable';
  const [wholeText, fractionalText = ''] = value.trim().split('.');
  if (!/^\d+$/.test(wholeText) || !/^\d*$/.test(fractionalText)) {
    return `${value} ratio`;
  }

  const digits = `${wholeText}${fractionalText}`;
  const decimalIndex = wholeText.length + 2;
  const percentage =
    decimalIndex >= digits.length
      ? `${digits}${'0'.repeat(decimalIndex - digits.length)}`
      : `${digits.slice(0, decimalIndex)}.${digits.slice(decimalIndex)}`;
  const [percentageWhole, percentageFraction = ''] = percentage.split('.');
  const normalizedWhole = percentageWhole.replace(/^0+/, '') || '0';
  const normalizedFraction = percentageFraction.replace(/0+$/, '');
  return `${normalizedWhole}${normalizedFraction ? `.${normalizedFraction}` : ''}%`;
}

const stopAccepted = (value: string) =>
  value === 'STOP_REQUESTED' || value === 'STOPPED';

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

function PaperStatusFacts({
  data,
  lifecycleState,
}: {
  data: PaperStatus;
  lifecycleState: string;
}) {
  const { timeZone } = useDisplayTimeZone();
  const activation = data.activation;
  return (
    <div className="space-y-4">
      <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        <Fact label="Strategy" value={activation.strategyKey} />
        <Fact
          label="StrategyVersion"
          value={`v${activation.strategyVersionNumber}`}
        />
        <Fact
          label="Risk per trade"
          value={formatRiskPercentage(activation.riskPerTrade)}
        />
        <Fact
          label="Lifecycle state"
          value={formatPaperLifecycle(lifecycleState)}
        />
        <Fact
          label="Operational phase"
          value={formatPaperOperationalPhase(activation.operationalPhase)}
        />
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
  const lifecycle = formatPaperLifecycle(data.activation.lifecycleState);
  const lifecycleClass =
    data.activation.lifecycleState === 'BLOCKED' ||
    data.activation.lifecycleState === 'FAILED'
      ? 'status status-danger'
      : 'status status-success';
  return (
    <div className="space-y-3">
      <p className={lifecycleClass}>{lifecycle}</p>
      <p className="text-sm text-atlas-foreground-muted">
        Phase{' '}
        <span>
          {formatPaperOperationalPhase(data.activation.operationalPhase)}
        </span>
      </p>
    </div>
  );
}

function StopConfirmation({
  submitting,
  onCancel,
  onConfirm,
}: {
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="paper-stop-heading"
      className="space-y-4 border border-atlas-warning bg-atlas-warning-muted p-4"
    >
      <div>
        <h3 id="paper-stop-heading" className="font-semibold">
          Stop the PAPER runtime session?
        </h3>
        <p className="mt-2 text-sm leading-6 text-atlas-warning">
          Stopping PAPER does not close or modify broker positions or orders.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="action-secondary"
          disabled={submitting}
          onClick={onCancel}
        >
          Keep running
        </button>
        <button
          type="button"
          className="action-primary"
          disabled={submitting}
          onClick={onConfirm}
        >
          {submitting ? 'Requesting stop…' : 'Confirm stop'}
        </button>
      </div>
    </div>
  );
}

export function PaperActiveStatusSection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const loader = useCallback(() => atlasApi.activePaperStatus(), []);
  const { state: activeState, retry: retryActiveRead } =
    useReadResource<PaperStatus | null>(loader);
  const [retainedActivationId, setRetainedActivationId] = useState<
    string | null
  >(null);
  const [detailState, setDetailState] =
    useState<ReadState<PaperStatus | null> | null>(null);
  const [detailRetry, setDetailRetry] = useState(0);
  const [detailPollAttempt, setDetailPollAttempt] = useState(0);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [stopSubmitting, setStopSubmitting] = useState(false);
  const [stopRequested, setStopRequested] = useState(false);
  const [stopError, setStopError] = useState('');
  const discoveredActiveRef = useRef(false);
  const detailRequestRef = useRef(0);
  const stopSubmittingRef = useRef(false);

  useEffect(() => {
    if (activeState.status !== 'ready' || discoveredActiveRef.current) return;

    discoveredActiveRef.current = true;
    if (activeState.data === null) {
      // Preserve the active-status empty result as the retained session state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDetailState({ status: 'ready', data: null });
      return;
    }

    // The active read establishes the durable ID that detail polling retains.
    setRetainedActivationId(activeState.data.activation.activationId);
    setDetailState({ status: 'ready', data: activeState.data });
  }, [activeState]);

  const observedLifecycle =
    detailState?.status === 'ready' && detailState.data
      ? detailState.data.activation.lifecycleState
      : null;

  useEffect(() => {
    if (
      !retainedActivationId ||
      (observedLifecycle !== null && isTerminalLifecycle(observedLifecycle))
    ) {
      return;
    }

    let cancelled = false;
    const timer = globalThis.setTimeout(() => {
      const requestNumber = ++detailRequestRef.current;
      atlasApi.paperStatus(retainedActivationId).then(
        (data) => {
          if (cancelled || requestNumber !== detailRequestRef.current) return;
          setDetailState({ status: 'ready', data });
          if (!isTerminalLifecycle(data.activation.lifecycleState)) {
            setDetailPollAttempt((attempt) => attempt + 1);
          }
        },
        (error: unknown) => {
          if (cancelled || requestNumber !== detailRequestRef.current) return;
          setDetailState({ status: 'error', error });
        },
      );
    }, PAPER_STATUS_POLL_MS);

    return () => {
      cancelled = true;
      globalThis.clearTimeout(timer);
    };
  }, [detailPollAttempt, detailRetry, observedLifecycle, retainedActivationId]);

  const retryDetail = () => {
    setDetailState({ status: 'loading' });
    setDetailRetry((attempt) => attempt + 1);
  };

  const retryActive = () => {
    discoveredActiveRef.current = false;
    setDetailState(null);
    retryActiveRead();
  };

  const sessionState: ReadState<PaperStatus | null> =
    detailState ?? activeState;
  const sessionData =
    sessionState.status === 'ready' ? sessionState.data : null;
  const sessionLifecycle = sessionData?.activation.lifecycleState ?? null;
  const displayedLifecycle =
    sessionData &&
    stopRequested &&
    !isTerminalLifecycle(sessionData.activation.lifecycleState)
      ? 'STOP_REQUESTED'
      : sessionLifecycle;
  const terminal = sessionLifecycle
    ? isTerminalLifecycle(sessionLifecycle)
    : false;
  const isStopping =
    sessionData !== null &&
    (sessionLifecycle === 'STOP_REQUESTED' || stopRequested) &&
    !terminal;

  const stop = async () => {
    if (
      stopSubmittingRef.current ||
      !retainedActivationId ||
      !sessionData ||
      terminal ||
      sessionLifecycle === 'STOP_REQUESTED'
    ) {
      return;
    }

    stopSubmittingRef.current = true;
    setStopSubmitting(true);
    setStopError('');
    const requestNumber = ++detailRequestRef.current;

    try {
      const response = await atlasApi.stopPaper(retainedActivationId, {
        reason: PAPER_STOP_REASON,
      });
      if (requestNumber !== detailRequestRef.current) return;

      setStopRequested(!isTerminalLifecycle(response.lifecycleState));
      setStopDialogOpen(false);
      setStopError('');
      if (sessionData) {
        setDetailState({
          status: 'ready',
          data: { ...sessionData, activation: response },
        });
      }
    } catch (error) {
      if (error instanceof ApiError) {
        setStopError(`Stop was not accepted. ${error.message}`);
        setStopDialogOpen(false);
      } else {
        try {
          const detailRequestNumber = ++detailRequestRef.current;
          const detail = await atlasApi.paperStatus(retainedActivationId);
          if (detailRequestNumber !== detailRequestRef.current) return;

          setDetailState({ status: 'ready', data: detail });
          if (stopAccepted(detail.activation.lifecycleState)) {
            setStopRequested(true);
            setStopDialogOpen(false);
            setStopError('');
          } else {
            setStopRequested(false);
            setStopDialogOpen(false);
            setStopError(
              'Stop outcome is uncertain. Atlas did not confirm STOP_REQUESTED or STOPPED. Retry explicitly.',
            );
          }
        } catch (readError) {
          setStopRequested(false);
          setStopDialogOpen(false);
          setStopError(
            `Stop outcome is uncertain. The read-only status check failed: ${readError instanceof Error ? readError.message : 'Atlas could not confirm the session state.'}`,
          );
        }
      }
    } finally {
      stopSubmittingRef.current = false;
      setStopSubmitting(false);
    }
  };

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
      {sessionState.status === 'loading' && (
        <LoadingState label={compact ? 'runtime' : 'Runtime status'} />
      )}
      {sessionState.status === 'error' &&
        (compact ? (
          <div className="space-y-3">
            <UnavailableState>Runtime unavailable</UnavailableState>
            <button
              type="button"
              onClick={sessionState === activeState ? retryActive : retryDetail}
              className="text-sm font-medium text-atlas-primary underline-offset-2 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : (
          <ReadError
            error={sessionState.error}
            retry={sessionState === activeState ? retryActive : retryDetail}
          />
        ))}
      {sessionState.status === 'ready' &&
        (sessionState.data === null ? (
          compact ? (
            <EmptyState>No active runtime</EmptyState>
          ) : (
            <div className="space-y-4">
              <EmptyState>No active PAPER session</EmptyState>
              <Link href="/paper/activate" className="action-primary">
                Activate PAPER
              </Link>
            </div>
          )
        ) : (
          <div className="space-y-5">
            {compact ? (
              <CompactPaperStatus data={sessionState.data} />
            ) : (
              <>
                {stopError && (
                  <p
                    role="alert"
                    className="border-l-2 border-atlas-warning bg-atlas-warning-muted p-3 text-sm text-atlas-warning"
                  >
                    {stopError}
                  </p>
                )}
                <PaperStatusFacts
                  data={sessionState.data}
                  lifecycleState={displayedLifecycle ?? sessionLifecycle ?? ''}
                />
                {isStopping && (
                  <p className="text-sm text-atlas-warning" role="status">
                    Stop requested. Atlas is waiting for durable terminal
                    session state.
                  </p>
                )}
                {!terminal && !isStopping && (
                  <>
                    <button
                      type="button"
                      className="action-secondary"
                      onClick={() => {
                        setStopError('');
                        setStopDialogOpen(true);
                      }}
                    >
                      Stop PAPER
                    </button>
                    {stopDialogOpen && (
                      <StopConfirmation
                        submitting={stopSubmitting}
                        onCancel={() => setStopDialogOpen(false)}
                        onConfirm={stop}
                      />
                    )}
                  </>
                )}
              </>
            )}
          </div>
        ))}
    </section>
  );
}

export function PaperStatus() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
      <header className="max-w-3xl">
        <p className="mb-2 text-sm font-medium text-atlas-primary">
          PAPER supervision
        </p>
        <h1
          id="paper-heading"
          className="text-3xl font-semibold tracking-tight"
        >
          PAPER
        </h1>
        <p className="mt-3 text-sm leading-6 text-atlas-foreground-muted">
          Supervise the PAPER runtime separately from current broker exposure.
          Stopping the runtime does not close or modify broker positions or
          orders.
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
