'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FormEvent } from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { atlasApi, ApiError } from '../lib/api-client';
import { formatInstrumentDisplay } from '../lib/instrument';
import {
  percentageToDecimalRatio,
  PAPER_ACTIVATION_CONFIRMATION,
} from '../lib/paper-control';
import { parameterDefaults, object, text } from './experiments/shared';
import type { ReadState } from './read-resource';
import {
  EmptyState,
  LoadingState,
  ReadError,
  UnavailableState,
  useReadResource,
} from './read-resource';
import type { components } from '../lib/api.generated';

type StrategyCatalogItem = components['schemas']['StrategyCatalogItemResponse'];
type StrategyDetail = components['schemas']['StrategyDetailResponse'];
type StrategyVersion = components['schemas']['StrategyVersionHistoryResponse'];
type PaperCapability = components['schemas']['PaperCapabilityResponse'];
type PaperStatus = components['schemas']['PaperRuntimeStatusResponse'];
type PaperBrokerState = components['schemas']['PaperBrokerStateResponse'];
type ParameterValues = Record<string, string>;

type DetailState = { status: 'idle' } | ReadState<StrategyDetail>;
type ActivationOutcome = 'idle' | 'retry' | 'conflict';

type ReviewSnapshot = {
  strategyKey: string;
  strategyName: string;
  strategyVersionId: string;
  strategyVersionLabel: string;
  methodology: string;
  parameters: Record<string, unknown>;
  riskPercentage: string;
  riskPerTrade: string;
  provider: string;
  environment: string;
  instrument: string;
  activationRequestId: string;
};

const display = (value: unknown, fallback = 'Unavailable') =>
  value === null || value === undefined || value === ''
    ? fallback
    : String(value);

const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : 'Atlas could not complete that request.';

const instrumentLabel = (instrument: string) => {
  const formatted = formatInstrumentDisplay(instrument);
  return formatted === 'EURUSD'
    ? 'EUR/USD'
    : formatted || 'Instrument unavailable';
};

const environmentLabel = (provider: string, environment: string) =>
  [
    provider,
    environment.toUpperCase() === 'PRACTICE' ? 'Practice' : environment,
  ]
    .map((value) => value.trim())
    .filter(Boolean)
    .join(' ') || 'Provider environment unavailable';

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-atlas-border pt-3">
      <dt className="text-xs text-atlas-foreground-muted">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{value}</dd>
    </div>
  );
}

function PreflightRow({
  label,
  children,
  tone = 'neutral',
}: {
  label: string;
  children: React.ReactNode;
  tone?: 'neutral' | 'positive' | 'warning' | 'negative';
}) {
  const toneClass = {
    neutral: 'text-atlas-foreground-muted',
    positive: 'text-atlas-positive',
    warning: 'text-atlas-warning',
    negative: 'text-atlas-negative',
  }[tone];
  return (
    <div className="flex flex-col gap-1 border-t border-atlas-border pt-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <dt className="text-sm font-medium">{label}</dt>
      <dd className={`text-sm sm:max-w-[70%] sm:text-right ${toneClass}`}>
        {children}
      </dd>
    </div>
  );
}

function ParameterEditor({
  schema,
  parameters,
  errors,
  disabled,
  onChange,
}: {
  schema: Record<string, unknown>[];
  parameters: ParameterValues;
  errors: Record<string, string>;
  disabled: boolean;
  onChange: (key: string, value: string) => void;
}) {
  if (schema.length === 0) {
    return (
      <EmptyState>
        This StrategyVersion has no configurable parameters.
      </EmptyState>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {schema.map((value) => {
        const descriptor = object(value);
        const key = text(descriptor.key, '');
        const type = text(descriptor.type, 'string');
        const label = text(descriptor.label, key);
        const error = errors[key];
        const allowed = Array.isArray(descriptor.allowedValues)
          ? descriptor.allowedValues.map(String)
          : [];
        const fixed =
          descriptor.min !== undefined &&
          descriptor.max !== undefined &&
          String(descriptor.min) === String(descriptor.max);

        return (
          <div key={key} className="flex flex-col gap-2 text-sm font-medium">
            <label htmlFor={key}>{label}</label>
            {type === 'enum' || type === 'boolean' ? (
              <select
                id={key}
                aria-describedby={`${key}-hint ${key}-error`}
                aria-invalid={Boolean(error)}
                className="form-control"
                disabled={disabled}
                value={parameters[key] ?? ''}
                onChange={(event) => onChange(key, event.target.value)}
              >
                {type === 'enum' && parameters[key] === '' && (
                  <option value="">Choose a value</option>
                )}
                {(type === 'boolean' ? ['true', 'false'] : allowed).map(
                  (item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ),
                )}
              </select>
            ) : (
              <input
                id={key}
                aria-describedby={`${key}-hint ${key}-error`}
                aria-invalid={Boolean(error)}
                className="form-control"
                disabled={disabled}
                inputMode={
                  type === 'integer'
                    ? 'numeric'
                    : type === 'decimal'
                      ? 'decimal'
                      : undefined
                }
                readOnly={fixed}
                type="text"
                value={parameters[key] ?? ''}
                onChange={(event) => onChange(key, event.target.value)}
              />
            )}
            <span
              id={`${key}-hint`}
              className="text-xs font-normal text-atlas-foreground-muted"
            >
              {fixed
                ? 'Fixed by methodology.'
                : type === 'enum'
                  ? `Allowed: ${allowed.join(', ')}`
                  : type}
              {descriptor.description
                ? ` · ${text(descriptor.description)}`
                : ''}
              {descriptor.min !== undefined &&
              descriptor.max !== undefined &&
              !fixed
                ? ` · ${text(descriptor.min)} to ${text(descriptor.max)}`
                : ''}
            </span>
            {error && (
              <span
                id={`${key}-error`}
                className="text-xs font-normal text-atlas-negative"
              >
                {error}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Preflight({
  capability,
  active,
  broker,
}: {
  capability: ReturnType<typeof useReadResource<PaperCapability>>['state'];
  active: ReturnType<typeof useReadResource<PaperStatus | null>>['state'];
  broker: ReturnType<typeof useReadResource<PaperBrokerState>>['state'];
}) {
  return (
    <section
      aria-labelledby="paper-activation-preflight-heading"
      className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5"
    >
      <div>
        <h2
          id="paper-activation-preflight-heading"
          className="text-lg font-semibold"
        >
          Before approval
        </h2>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
          These read-only checks inform this screen. Atlas runtime performs its
          own fresh startup checks before any PAPER execution.
        </p>
      </div>
      <dl className="flex flex-col gap-4">
        {capability.status === 'loading' && (
          <PreflightRow label="PAPER capability">
            <LoadingState label="capability" />
          </PreflightRow>
        )}
        {capability.status === 'error' && (
          <PreflightRow label="PAPER capability" tone="negative">
            <span>Unavailable. {errorMessage(capability.error)}</span>
          </PreflightRow>
        )}
        {capability.status === 'ready' && (
          <PreflightRow
            label="PAPER capability"
            tone={capability.data.available ? 'positive' : 'warning'}
          >
            {capability.data.available
              ? `${environmentLabel(capability.data.provider, capability.data.environment)} · ${instrumentLabel(capability.data.instrument)} available`
              : `Unavailable. Reason: ${display(capability.data.reasonCode, 'No reason returned.')}`}
          </PreflightRow>
        )}

        {active.status === 'loading' && (
          <PreflightRow label="Active PAPER session">
            <LoadingState label="active session" />
          </PreflightRow>
        )}
        {active.status === 'error' && (
          <PreflightRow label="Active PAPER session" tone="negative">
            <span>
              Unavailable. Atlas cannot establish that no session is active.
            </span>
          </PreflightRow>
        )}
        {active.status === 'ready' && (
          <PreflightRow
            label="Active PAPER session"
            tone={active.data ? 'warning' : 'positive'}
          >
            {active.data ? (
              <span>
                An active PAPER session already exists.{' '}
                <Link className="underline underline-offset-2" href="/paper">
                  View PAPER status
                </Link>
              </span>
            ) : (
              'No active PAPER session reported.'
            )}
          </PreflightRow>
        )}

        {broker.status === 'loading' && (
          <PreflightRow label="Broker exposure">
            <LoadingState label="broker state" />
          </PreflightRow>
        )}
        {broker.status === 'error' && (
          <PreflightRow label="Broker exposure" tone="negative">
            <span>
              Unavailable. Open broker Trades are unknown, so approval is
              blocked.
            </span>
          </PreflightRow>
        )}
        {broker.status === 'ready' && broker.data.openTrades.length > 0 && (
          <PreflightRow label="Broker exposure" tone="warning">
            {`${broker.data.openTrades.length} visible open broker Trade${broker.data.openTrades.length === 1 ? '' : 's'} found. Approval is blocked.`}
          </PreflightRow>
        )}
        {broker.status === 'ready' && broker.data.openTrades.length === 0 && (
          <PreflightRow label="Broker exposure" tone="warning">
            No open broker Trades were returned. This is not proof of a flat
            account.
          </PreflightRow>
        )}
      </dl>
    </section>
  );
}

export function PaperActivation() {
  const router = useRouter();
  const catalogLoader = useCallback(() => atlasApi.listStrategies(), []);
  const capabilityLoader = useCallback(() => atlasApi.paperCapability(), []);
  const activeLoader = useCallback(() => atlasApi.activePaperStatus(), []);
  const brokerLoader = useCallback(() => atlasApi.paperBrokerState(), []);
  const catalog = useReadResource(catalogLoader);
  const capability = useReadResource<PaperCapability>(capabilityLoader);
  const active = useReadResource<PaperStatus | null>(activeLoader);
  const broker = useReadResource<PaperBrokerState>(brokerLoader);
  const [strategyKey, setStrategyKey] = useState('');
  const [detail, setDetail] = useState<DetailState>({ status: 'idle' });
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [versionId, setVersionId] = useState('');
  const [parameters, setParameters] = useState<ParameterValues>({});
  const [riskPercentage, setRiskPercentage] = useState('');
  const [review, setReview] = useState<ReviewSnapshot | null>(null);
  const [confirmation, setConfirmation] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [activationOutcome, setActivationOutcome] =
    useState<ActivationOutcome>('idle');
  const submittingRef = useRef(false);

  useEffect(() => {
    if (!strategyKey) {
      // Reset the detail read when the trader clears the Strategy selection.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDetail({ status: 'idle' });
      return;
    }

    let current = true;
    setDetail({ status: 'loading' });
    atlasApi.getStrategy(strategyKey).then(
      (value) => {
        if (current) setDetail({ status: 'ready', data: value });
      },
      (error: unknown) => {
        if (current) setDetail({ status: 'error', error });
      },
    );
    return () => {
      current = false;
    };
  }, [strategyKey, detailAttempt]);

  const invalidateReview = useCallback(() => {
    setReview(null);
    setConfirmation('');
    setFormError('');
    setActivationOutcome('idle');
  }, []);

  const selectedCatalogItem: StrategyCatalogItem | undefined =
    catalog.state.status === 'ready'
      ? catalog.state.data.items.find(
          (item) => item.strategyKey === strategyKey,
        )
      : undefined;
  const selectedVersion: StrategyVersion | undefined =
    detail.status === 'ready'
      ? detail.data.versions.find((version) => version.id === versionId)
      : undefined;
  const schema = selectedVersion?.parameterSchema ?? [];
  const parameterErrors: Record<string, string> = Object.fromEntries(
    schema.flatMap((value) => {
      const descriptor = object(value);
      const key = text(descriptor.key, '');
      const raw = parameters[key] ?? '';
      if (!key || raw.trim() === '') {
        return descriptor.nullable === true ? [] : [[key, 'Enter a value.']];
      }
      const type = text(descriptor.type, 'string');
      if (type === 'string') return [];
      if (type === 'enum') {
        const allowed = Array.isArray(descriptor.allowedValues)
          ? descriptor.allowedValues.map(String)
          : [];
        return allowed.includes(raw) ? [] : [[key, 'Choose an allowed value.']];
      }
      if (type === 'boolean') {
        return raw === 'true' || raw === 'false'
          ? []
          : [[key, 'Choose true or false.']];
      }
      const parsed = Number(raw);
      if (
        !Number.isFinite(parsed) ||
        (type === 'integer' && !Number.isInteger(parsed))
      ) {
        return [
          [
            key,
            type === 'integer'
              ? 'Enter a whole number.'
              : 'Enter a finite decimal.',
          ],
        ];
      }
      const minimum = Number(descriptor.min);
      const maximum = Number(descriptor.max);
      if (Number.isFinite(minimum) && parsed < minimum) {
        return [[key, `Must be at least ${text(descriptor.min)}.`]];
      }
      if (Number.isFinite(maximum) && parsed > maximum) {
        return [[key, `Must be at most ${text(descriptor.max)}.`]];
      }
      return [];
    }),
  );
  const risk = riskPercentage.trim();
  const riskError = !risk
    ? 'Enter Risk per trade as a percentage.'
    : (() => {
        try {
          percentageToDecimalRatio(risk);
          return '';
        } catch (error) {
          return errorMessage(error);
        }
      })();
  const preflightReady =
    capability.state.status === 'ready' &&
    active.state.status === 'ready' &&
    broker.state.status === 'ready';
  const preflightAllows =
    preflightReady &&
    capability.state.status === 'ready' &&
    capability.state.data.available &&
    active.state.status === 'ready' &&
    active.state.data === null &&
    broker.state.status === 'ready' &&
    broker.state.data.openTrades.length === 0;
  const configurationValid = Boolean(
    strategyKey &&
    detail.status === 'ready' &&
    selectedVersion?.executionAvailable &&
    versionId &&
    Object.keys(parameterErrors).length === 0 &&
    !riskError,
  );
  const canReview = configurationValid && preflightAllows && !submitting;
  const availableVersions =
    detail.status === 'ready'
      ? detail.data.versions.filter((version) => version.executionAvailable)
      : [];

  const changeStrategy = (nextStrategyKey: string) => {
    invalidateReview();
    setStrategyKey(nextStrategyKey);
    setDetailAttempt((attempt) => attempt + 1);
    setVersionId('');
    setParameters({});
  };

  const changeVersion = (nextVersionId: string) => {
    invalidateReview();
    const nextVersion =
      detail.status === 'ready'
        ? detail.data.versions.find((version) => version.id === nextVersionId)
        : undefined;
    setVersionId(nextVersionId);
    setParameters(parameterDefaults(nextVersion));
  };

  const parameterChange = (key: string, value: string) => {
    invalidateReview();
    setParameters((current) => ({ ...current, [key]: value }));
  };

  const enterReview = () => {
    setFormError('');
    if (!canReview || !selectedVersion || capability.state.status !== 'ready') {
      setFormError(
        'Complete the configuration and all available preflight checks before review.',
      );
      return;
    }

    const reviewedParameters = Object.fromEntries(
      schema.map((value) => {
        const descriptor = object(value);
        const key = text(descriptor.key, '');
        const raw = parameters[key] ?? '';
        const type = text(descriptor.type, 'string');
        return [
          key,
          raw.trim() === ''
            ? raw
            : type === 'integer'
              ? Number(raw)
              : type === 'boolean'
                ? raw === 'true'
                : raw,
        ];
      }),
    );
    let riskRatio: string;
    try {
      riskRatio = percentageToDecimalRatio(risk);
    } catch (error) {
      setFormError(errorMessage(error));
      return;
    }
    if (!globalThis.crypto?.randomUUID) {
      setFormError(
        'This browser cannot create a secure activation review identity.',
      );
      return;
    }
    setReview({
      strategyKey,
      strategyName:
        detail.status === 'ready'
          ? detail.data.name
          : (selectedCatalogItem?.name ?? 'Strategy'),
      strategyVersionId: selectedVersion.id,
      strategyVersionLabel: `${selectedVersion.displayName} · v${selectedVersion.versionNumber}`,
      methodology: display(
        object(selectedVersion.methodology).summary,
        'Methodology unavailable',
      ),
      parameters: reviewedParameters,
      riskPercentage: risk,
      riskPerTrade: riskRatio,
      provider: capability.state.data.provider,
      environment: capability.state.data.environment,
      instrument: capability.state.data.instrument,
      activationRequestId: globalThis.crypto.randomUUID(),
    });
    setConfirmation('');
    setActivationOutcome('idle');
  };

  const resolveAmbiguousActivation = async (requestId: string) => {
    try {
      const current = await atlasApi.activePaperStatus();
      const currentId = current?.activation.activationId;
      if (current && currentId === requestId) {
        router.push('/paper');
        return;
      }
      if (current === null) {
        setActivationOutcome('retry');
        setFormError(
          'Activation outcome is unknown. No active session was found. Retry explicitly with this same review.',
        );
        return;
      }
      setActivationOutcome('conflict');
      setFormError(
        'Activation outcome is unresolved because a different active PAPER session exists. No retry was sent.',
      );
    } catch (error) {
      setActivationOutcome('retry');
      setFormError(
        `Activation outcome is unknown. The read-only status check failed: ${errorMessage(error)}`,
      );
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      submittingRef.current ||
      !review ||
      confirmation !== 'ACTIVATE PAPER' ||
      !preflightAllows ||
      activationOutcome === 'conflict'
    ) {
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    setFormError('');
    try {
      await atlasApi.activatePaper({
        activationRequestId: review.activationRequestId,
        strategyVersionId: review.strategyVersionId,
        parameters: review.parameters,
        riskPerTrade: review.riskPerTrade,
        confirmation: PAPER_ACTIVATION_CONFIRMATION,
      });
      router.push('/paper');
    } catch (error) {
      if (!(error instanceof ApiError)) {
        await resolveAmbiguousActivation(review.activationRequestId);
      } else {
        setFormError(`Activation was not accepted. ${errorMessage(error)}`);
      }
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <section
      aria-labelledby="paper-activation-heading"
      className="mx-auto flex w-full max-w-5xl flex-col gap-8"
    >
      <header className="max-w-3xl">
        <Link
          href="/paper"
          className="mb-5 inline-flex items-center text-sm text-atlas-foreground-muted hover:text-atlas-foreground"
        >
          PAPER status
        </Link>
        <p className="mb-2 text-sm font-medium text-atlas-warning">
          Capital approval workflow
        </p>
        <h1
          id="paper-activation-heading"
          className="text-3xl font-semibold tracking-tight"
        >
          Activate PAPER
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
          Review one immutable StrategyVersion and its Risk setting before
          authorizing Atlas to create PAPER Trades automatically when signals
          and Risk allow them.
        </p>
      </header>

      {formError && (
        <p
          role="alert"
          className="border-l-2 border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
        >
          {formError}
        </p>
      )}

      <Preflight
        capability={capability.state}
        active={active.state}
        broker={broker.state}
      />

      <form onSubmit={submit} className="flex flex-col gap-6">
        <fieldset className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <legend className="px-1 text-base font-medium">1 · Strategy</legend>
          <p className="max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
            Select the methodology first. The next step reads its immutable
            StrategyVersion history; frontend availability is not final PAPER
            approval.
          </p>
          {catalog.state.status === 'loading' && (
            <LoadingState label="Strategies" />
          )}
          {catalog.state.status === 'error' && (
            <ReadError error={catalog.state.error} retry={catalog.retry} />
          )}
          {catalog.state.status === 'ready' &&
            catalog.state.data.items.length === 0 && (
              <UnavailableState>
                No Strategies are available for selection.
              </UnavailableState>
            )}
          {catalog.state.status === 'ready' &&
            catalog.state.data.items.length > 0 && (
              <label className="flex max-w-xl flex-col gap-2 text-sm font-medium">
                Strategy
                <select
                  required
                  aria-label="Strategy"
                  className="form-control"
                  disabled={submitting}
                  value={strategyKey}
                  onChange={(event) => changeStrategy(event.target.value)}
                >
                  <option value="">Choose a Strategy</option>
                  {catalog.state.data.items.map((item) => (
                    <option key={item.strategyKey} value={item.strategyKey}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          {selectedCatalogItem && (
            <p className="border-t border-atlas-border pt-4 text-sm leading-6 text-atlas-foreground-muted">
              {selectedCatalogItem.description}
            </p>
          )}
        </fieldset>

        <fieldset className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <legend className="px-1 text-base font-medium">
            2 · Immutable StrategyVersion
          </legend>
          {!strategyKey && (
            <EmptyState>Choose a Strategy to load its versions.</EmptyState>
          )}
          {detail.status === 'loading' && (
            <LoadingState label="Strategy versions" />
          )}
          {detail.status === 'error' && (
            <ReadError
              error={detail.error}
              retry={() => changeStrategy(strategyKey)}
            />
          )}
          {detail.status === 'ready' && (
            <>
              <label className="flex max-w-xl flex-col gap-2 text-sm font-medium">
                StrategyVersion
                <select
                  required
                  aria-label="StrategyVersion"
                  className="form-control"
                  disabled={submitting}
                  value={versionId}
                  onChange={(event) => changeVersion(event.target.value)}
                >
                  <option value="">Choose a StrategyVersion</option>
                  {detail.data.versions.map((version) => (
                    <option
                      key={version.id}
                      value={version.id}
                      disabled={!version.executionAvailable}
                    >
                      {version.displayName} · v{version.versionNumber}
                      {!version.executionAvailable ? ' · unavailable' : ''}
                    </option>
                  ))}
                </select>
              </label>
              {detail.data.versions.length > 0 &&
                availableVersions.length === 0 && (
                  <UnavailableState>
                    Every StrategyVersion is unavailable for local execution. No
                    PAPER activation can be prepared.
                  </UnavailableState>
                )}
              {selectedVersion && (
                <div className="grid gap-4 border-t border-atlas-border pt-4 text-sm sm:grid-cols-3">
                  <Fact
                    label="Methodology"
                    value={display(object(selectedVersion.methodology).summary)}
                  />
                  <Fact
                    label="Market boundary"
                    value={`${instrumentLabel(text(object(selectedVersion.marketRequirements).instrument, ''))} · ${display(object(selectedVersion.marketRequirements).resolution, selectedVersion.timeframe)}`}
                  />
                  <Fact
                    label="Execution availability"
                    value="Available locally"
                  />
                </div>
              )}
            </>
          )}
        </fieldset>

        <fieldset className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
          <legend className="px-1 text-base font-medium">
            3 · Parameters and Risk
          </legend>
          <p className="max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
            Defaults come from the selected immutable StrategyVersion. Parameter
            validation improves this form only; the PAPER boundary remains
            authoritative.
          </p>
          {selectedVersion ? (
            <ParameterEditor
              schema={schema}
              parameters={parameters}
              errors={parameterErrors}
              disabled={submitting}
              onChange={parameterChange}
            />
          ) : (
            <EmptyState>
              Choose an available StrategyVersion to configure parameters.
            </EmptyState>
          )}
          <div className="border-t border-atlas-border pt-5">
            <div className="flex max-w-sm flex-col gap-2 text-sm font-medium">
              <label htmlFor="risk-per-trade">Risk per trade (%)</label>
              <input
                id="risk-per-trade"
                aria-describedby="risk-per-trade-hint risk-per-trade-error"
                aria-invalid={Boolean(riskError && risk)}
                className="form-control text-lg"
                disabled={submitting}
                inputMode="decimal"
                placeholder="Enter a percentage"
                type="text"
                value={riskPercentage}
                onChange={(event) => {
                  invalidateReview();
                  setRiskPercentage(event.target.value);
                }}
              />
              <span
                id="risk-per-trade-hint"
                className="text-xs font-normal text-atlas-foreground-muted"
              >
                Atlas Risk applies this percentage to fresh account equity when
                an eligible Trade is evaluated.
              </span>
              {riskError && risk && (
                <span
                  id="risk-per-trade-error"
                  className="text-xs font-normal text-atlas-negative"
                >
                  {riskError}
                </span>
              )}
            </div>
          </div>
        </fieldset>

        <section
          className="flex flex-col gap-4 rounded-lg border border-atlas-primary bg-atlas-primary-muted p-5"
          aria-labelledby="paper-review-heading"
        >
          <div>
            <p className="text-sm font-medium text-atlas-primary">
              4 · Review and authorization
            </p>
            <h2
              id="paper-review-heading"
              className="mt-1 text-xl font-semibold"
            >
              Freeze the approval before submission
            </h2>
          </div>
          {!review && (
            <>
              <p className="max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
                Review captures the exact StrategyVersion, parameters, Risk
                ratio, and configured PAPER boundary. Any authority-bearing
                change clears this review and its confirmation.
              </p>
              <button
                type="button"
                className="action-secondary self-start"
                disabled={!canReview}
                onClick={enterReview}
              >
                Review activation
              </button>
              {!preflightReady && (
                <p className="text-xs text-atlas-foreground-muted">
                  Waiting for all preflight reads.
                </p>
              )}
              {preflightReady && !preflightAllows && (
                <p className="text-xs text-atlas-warning">
                  Resolve the blocked preflight state before review.
                </p>
              )}
            </>
          )}
          {review && (
            <>
              <p className="border-l-2 border-atlas-warning bg-atlas-warning-muted p-4 text-sm leading-6 text-atlas-warning">
                This approval authorizes Atlas to create PAPER Trades
                automatically when the Strategy signals and Atlas Risk approves
                them, until the session stops or blocks. It does not submit a
                broker Order immediately.
              </p>
              <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
                <Fact label="Environment" value="PAPER" />
                <Fact
                  label="Provider"
                  value={environmentLabel(review.provider, review.environment)}
                />
                <Fact
                  label="Strategy"
                  value={`${review.strategyName} · ${review.strategyKey}`}
                />
                <Fact
                  label="Immutable StrategyVersion"
                  value={review.strategyVersionLabel}
                />
                <Fact label="Methodology" value={review.methodology} />
                <Fact
                  label="Instrument"
                  value={`${instrumentLabel(review.instrument)} · current supported market boundary`}
                />
                <Fact
                  label="Risk per trade"
                  value={`${review.riskPercentage}% (wire ratio ${review.riskPerTrade})`}
                />
              </dl>
              <div className="border-t border-atlas-border pt-4">
                <p className="text-xs text-atlas-foreground-muted">
                  Reviewed parameters
                </p>
                <pre className="mt-2 max-w-full overflow-x-auto rounded bg-atlas-surface px-3 py-3 text-xs leading-5 text-atlas-foreground">
                  {JSON.stringify(review.parameters, null, 2)}
                </pre>
              </div>
              <details className="border-t border-atlas-border pt-4 text-xs">
                <summary className="cursor-pointer font-medium">
                  Frozen review identity
                </summary>
                <p className="mt-2 break-all font-mono text-atlas-foreground-muted">
                  {review.activationRequestId}
                </p>
              </details>
              <label className="flex max-w-md flex-col gap-2 border-t border-atlas-border pt-5 text-sm font-medium">
                Type{' '}
                <span className="font-mono text-atlas-primary">
                  ACTIVATE PAPER
                </span>{' '}
                to authorize
                <input
                  aria-label="Activation confirmation"
                  className="form-control"
                  disabled={submitting}
                  type="text"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                />
              </label>
              <button
                type="submit"
                className="action-primary self-start"
                disabled={
                  submitting ||
                  confirmation !== 'ACTIVATE PAPER' ||
                  activationOutcome === 'conflict' ||
                  !preflightAllows
                }
              >
                {submitting
                  ? 'Checking activation outcome…'
                  : activationOutcome === 'retry'
                    ? 'Retry activation with same review'
                    : 'Activate PAPER trading'}
              </button>
              {activationOutcome === 'retry' && (
                <p className="text-xs text-atlas-warning">
                  No automatic retry was sent. This button will reuse the frozen
                  review ID.
                </p>
              )}
              {activationOutcome === 'conflict' && (
                <p className="text-xs text-atlas-warning">
                  A different active session was found. Return to{' '}
                  <Link className="underline" href="/paper">
                    PAPER status
                  </Link>
                  .
                </p>
              )}
            </>
          )}
        </section>
      </form>
    </section>
  );
}
