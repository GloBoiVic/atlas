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
import { utcDate, quarterHourNow } from './shared';
import type { ParameterValues } from './shared';
import {
  iso,
  dateInput,
  object,
  text,
  strategyIdentity,
  statusOf,
  dateLabel,
  errorMessage,
  productNextAction,
  scalarFields,
  parameterDefaults,
  snapshotLabel,
  snapshotOptionState,
  diagnosticLabel,
  formattedMetric,
  metricState,
  priceLabel,
  moneyLabel,
  rLabel,
  percentLabel,
} from './shared';

import { StatusBadge, ErrorPanel } from './load-status';

export function ExperimentForm() {
  const router = useRouter();
  const search = useSearchParams();
  const requestedStrategyVersion = search.get('strategyVersionId') ?? '';
  const [options, setOptions] = useState<Json>({});
  const [formError, setFormError] = useState<unknown>('');
  const [coverage, setCoverage] = useState<Json | null>(null);
  const [validating, setValidating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [strategy, setStrategy] = useState('');
  const [snapshot, setSnapshot] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [capital, setCapital] = useState('10000');
  const [risk, setRisk] = useState('0.01');
  const [slippage, setSlippage] = useState('0');
  const [commission, setCommission] = useState('0');
  const [parameters, setParameters] = useState<ParameterValues>({});
  const [capability, setCapability] = useState<Json | null>(null);
  const [historicalLoad, setHistoricalLoad] = useState<Json | null>(null);
  const [loadMessage, setLoadMessage] = useState<unknown>('');
  const [pollFailures, setPollFailures] = useState(0);
  const [pollPaused, setPollPaused] = useState(false);
  const [inventory, setInventory] = useState<Json | null>(null);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const historicalLoadId = useRef('');
  useEffect(() => {
    atlasApi
      .configurationOptions()
      .then((value) => {
        const data = object(value);
        setOptions(data);
        const versions = Array.isArray(data.strategyVersions)
          ? data.strategyVersions
          : [];
        const snapshots = Array.isArray(data.datasetSnapshots)
          ? data.datasetSnapshots
          : [];
        const available = versions.filter(
          (value) => object(value).executionAvailable !== false,
        );
        const preferred = [...available].sort(
          (a, b) => Number(object(b).version) - Number(object(a).version),
        )[0];
        const requested = available.find(
          (value) => text(object(value).id, '') === requestedStrategyVersion,
        );
        const initialVersion = requested ?? preferred;
        setStrategy(text(object(initialVersion).id, ''));
        setParameters(parameterDefaults(initialVersion));
        const initialSnapshot = snapshots.find(
          (value) => !snapshotOptionState(object(value), snapshots).disabled,
        );
        setSnapshot(text(object(initialSnapshot).id, ''));
      })
      .catch((error) => setFormError(error))
      .finally(() => setOptionsLoading(false));
  }, [requestedStrategyVersion]);
  const refreshOptions = useCallback(async () => {
    const value = object(await atlasApi.configurationOptions());
    setOptions(value);
    const nextSnapshots = Array.isArray(value.datasetSnapshots)
      ? value.datasetSnapshots
      : [];
    return nextSnapshots;
  }, []);
  useEffect(() => {
    void Promise.allSettled([
      atlasApi.historicalCapability(),
      atlasApi.activeHistoricalLoad(),
    ]).then(([cap, active]) => {
      if (cap.status === 'fulfilled') setCapability(object(cap.value));
      else {
        // Backend on old branch (before 0008) has no /historical-data/* → 404 HTTP_404. Treat as unavailable, not a red error on reload.
        const reason = cap.reason;
        if (
          reason instanceof ApiError &&
          (reason.code === 'HTTP_404' || reason.status === 404)
        )
          setCapability({ available: false });
      }
      if (active.status === 'fulfilled') {
        const value = active.value === null ? null : object(active.value);
        setHistoricalLoad(value);
        historicalLoadId.current = text(object(value).id, '');
      } else {
        // Initial page load never shows a red ErrorPanel — missing active load is normal (null), old-backend 404 is handled via capability.
        // Real explicit-load errors are surfaced only after you click Load/Validate.
      }
    });
  }, []);
  const pollLoad = useCallback(async (id: string) => {
    if (!id || historicalLoadId.current !== id) return null;
    try {
      const value = object(await atlasApi.historicalLoadStatus(id));
      if (historicalLoadId.current !== id) return null;
      setHistoricalLoad(value);
      setPollFailures(0);
      return value;
    } catch (error) {
      if (historicalLoadId.current !== id) return null;
      if (error instanceof ApiUnavailableError)
        setPollFailures((value) => value + 1);
      else setLoadMessage(error);
      return null;
    }
  }, []);
  const status = text(historicalLoad?.status, '');
  useEffect(() => {
    if (
      !historicalLoad ||
      (status !== 'PENDING' && status !== 'RUNNING') ||
      pollPaused ||
      pollFailures >= 3
    )
      return;
    const timer = window.setInterval(
      () => void pollLoad(historicalLoadId.current),
      1000,
    );
    return () => window.clearInterval(timer);
    // The request id is deliberately read from the ref: status payload objects change every tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, pollPaused, pollFailures]);
  const invalidate = () => setCoverage(null);
  const versions = Array.isArray(options.strategyVersions)
    ? options.strategyVersions
    : [];
  const snapshots = Array.isArray(options.datasetSnapshots)
    ? options.datasetSnapshots
    : [];
  const versionsMap = new Map(
    versions.map((value) => [text(object(value).id, ''), object(value)]),
  );
  const selectedVersion = object(
    versions.find((value) => text(object(value).id) === strategy),
  );
  const schema = Array.isArray(selectedVersion.parameterSchema)
    ? selectedVersion.parameterSchema
    : [];
  const requiredHistoricalContextBars = Number(
    selectedVersion.requiredHistoricalContextBars,
  );
  const strategyReady = Boolean(
    strategy &&
    versionsMap.has(strategy) &&
    selectedVersion.executionAvailable !== false &&
    Number.isFinite(requiredHistoricalContextBars) &&
    requiredHistoricalContextBars >= 0,
  );
  const loadStart = (() => {
    const instant = utcDate(start);
    if (!instant || !Number.isFinite(requiredHistoricalContextBars))
      return null;
    instant.setUTCMinutes(
      instant.getUTCMinutes() - requiredHistoricalContextBars * 15,
    );
    return instant;
  })();
  const tradingEnd = utcDate(end);
  const loadDurationDays =
    loadStart && tradingEnd
      ? (tradingEnd.getTime() - loadStart.getTime()) / 86400000
      : null;
  const loadRangeTooLarge = loadDurationDays !== null && loadDurationDays > 90;
  const loadRangeLabel =
    loadStart && tradingEnd
      ? `${formatInstant(loadStart.toISOString(), 'UTC')} → ${formatInstant(tradingEnd.toISOString(), 'UTC')}`
      : 'Choose valid UTC start and end times.';
  const applyPreset = (kind: '1W' | '1M' | '3M') => {
    if (!strategyReady || !Number.isFinite(requiredHistoricalContextBars))
      return;
    const anchor = utcDate(end) ?? utcDate(quarterHourNow()) ?? new Date();
    if (!anchor) return;
    anchor.setUTCMinutes(Math.floor(anchor.getUTCMinutes() / 15) * 15, 0, 0);
    const nextStart = new Date(anchor);
    if (kind === '1W') nextStart.setUTCDate(nextStart.getUTCDate() - 7);
    else
      nextStart.setUTCMonth(nextStart.getUTCMonth() - (kind === '1M' ? 1 : 3));
    const toInput = (date: Date) =>
      `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}T${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}`;
    setEnd(toInput(anchor));
    setStart(toInput(nextStart));
    invalidate();
  };
  useEffect(() => {
    const valid = Boolean(
      strategy && snapshot && iso(start) && iso(end) && iso(start)! < iso(end)!,
    );
    if (!valid) {
      const timer = window.setTimeout(() => setInventory(null), 0);
      return () => window.clearTimeout(timer);
    }
    let current = true;
    const loadingTimer = window.setTimeout(() => setInventoryLoading(true), 0);
    void atlasApi
      .validateCoverage({
        strategyVersionId: strategy,
        datasetSnapshotId: snapshot,
        tradingStart: iso(start)!,
        tradingEnd: iso(end)!,
      })
      .then((value) => {
        if (current) setInventory(object(value));
      })
      .catch(() => {
        if (current) setInventory(null);
      })
      .finally(() => {
        if (current) setInventoryLoading(false);
      });
    return () => {
      current = false;
      window.clearTimeout(loadingTimer);
    };
  }, [strategy, snapshot, start, end]);
  const parameterErrors = Object.fromEntries(
    schema.flatMap((value) => {
      const descriptor = object(value);
      const key = text(descriptor.key, '');
      const raw = parameters[key] ?? '';
      if (!key || raw.trim() === '') return [[key, 'Enter a value.']];
      const kind = text(descriptor.type, '');
      const parsed = kind === 'integer' ? Number(raw) : Number(raw);
      if (
        !Number.isFinite(parsed) ||
        (kind === 'integer' && !Number.isInteger(parsed))
      ) {
        return [
          [
            key,
            kind === 'integer'
              ? 'Enter a whole number.'
              : 'Enter a finite decimal.',
          ],
        ];
      }
      const minimum = Number(descriptor.min);
      const maximum = Number(descriptor.max);
      if (Number.isFinite(minimum) && parsed < minimum)
        return [[key, `Must be at least ${text(descriptor.min)}.`]];
      if (Number.isFinite(maximum) && parsed > maximum)
        return [[key, `Must be at most ${text(descriptor.max)}.`]];
      return [];
    }),
  );
  const loadActive = ['PENDING', 'RUNNING'].includes(
    text(historicalLoad?.status, ''),
  );
  const loadBlocksCreation = ['PENDING', 'RUNNING', 'FAILED'].includes(
    text(historicalLoad?.status, ''),
  );
  const progress = object(historicalLoad?.progress);
  const loadCoverage = object(historicalLoad?.coverage);
  const visibleDiagnostics = (value: unknown): unknown[] => {
    const diagnostics = object(value).diagnostics;
    return Array.isArray(diagnostics)
      ? (diagnostics as unknown[]).slice(0, 5)
      : [];
  };
  const validate = async (snapshotValue = snapshot) => {
    setFormError('');
    setValidating(true);
    try {
      setCoverage(
        object(
          await atlasApi.validateCoverage({
            strategyVersionId: strategy,
            datasetSnapshotId: snapshotValue,
            tradingStart: iso(start) ?? '',
            tradingEnd: iso(end) ?? '',
          }),
        ),
      );
    } catch (error) {
      setFormError(error);
    } finally {
      setValidating(false);
    }
  };
  useEffect(() => {
    if (text(historicalLoad?.status, '') !== 'COMPLETED') return;
    const period = `${dateLabel(historicalLoad?.tradingStart, 'UTC')} → ${dateLabel(historicalLoad?.tradingEnd, 'UTC')}`;
    const label = text(
      object(historicalLoad?.snapshot) &&
        snapshotLabel(object(object(historicalLoad?.snapshot))),
      text(historicalLoad?.displayLabel, 'Data ready'),
    );
    toast.success(`✓ Data ready — ${period}`, {
      description: `${label} selected. Validate and hit Run Experiment.`,
      duration: 6000,
    });
    // This asynchronous completion handler synchronizes durable API state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshOptions().then((items) => {
      const id = text(object(historicalLoad?.snapshot).id, '');
      const completedSnapshot = items.find(
        (item) => text(object(item).id) === id,
      );
      const completedSnapshotSelectable = Boolean(
        completedSnapshot &&
        !snapshotOptionState(completedSnapshot, items).disabled,
      );
      if (id && completedSnapshotSelectable) setSnapshot(id);
      if (id && completedSnapshotSelectable) void validate(id);
    });
    // Completion is a durable event; this effect intentionally runs once per request id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historicalLoad?.status, historicalLoad?.id]);
  const loadHistoricalData = async () => {
    setFormError('');
    setLoadMessage('');
    setCoverage(null);
    setPollPaused(false);
    setPollFailures(0);
    if (!strategyReady) {
      setLoadMessage(
        new ApiError(
          422,
          'STRATEGY_VERSION_NOT_FOUND',
          'Pick a StrategyVersion first — still loading',
        ),
      );
      return;
    }
    const tradingStart = iso(start);
    const tradingEnd = iso(end);
    if (!tradingStart || !tradingEnd || tradingStart >= tradingEnd) {
      setLoadMessage('Enter a valid 15-minute UTC period before loading data.');
      return;
    }
    if (loadRangeTooLarge) {
      setLoadMessage(
        'Shorten the period so the required-context-inclusive load range is 90 days or less.',
      );
      return;
    }
    try {
      const value = object(
        await atlasApi.createHistoricalLoad({
          strategyVersionId: strategy,
          tradingStart,
          tradingEnd,
        }),
      );
      historicalLoadId.current = text(value.id, '');
      setHistoricalLoad(value);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const id = text(object(error.details).requestId, '');
        if (id) {
          historicalLoadId.current = id;
          try {
            const attached = object(await atlasApi.historicalLoadStatus(id));
            setHistoricalLoad(attached);
            const s = text(attached.status, '');
            if (s === 'PENDING' || s === 'RUNNING') {
            }
          } catch (attachError) {
            setLoadMessage(attachError);
          }
        } else setLoadMessage(error);
      } else setLoadMessage(error);
    }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    setSubmitting(true);
    try {
      if (Object.keys(parameterErrors).length > 0)
        throw new Error(
          'Resolve the parameter errors before starting the Experiment.',
        );
      if (!coverage?.valid)
        throw new Error(
          'Validate coverage successfully before starting the Experiment.',
        );
      if (loadBlocksCreation)
        throw new Error(
          'Historical data loading must complete successfully before starting the Experiment.',
        );
      const tradingStart = iso(start);
      const tradingEnd = iso(end);
      if (!tradingStart || !tradingEnd)
        throw new Error('Enter a valid 15-minute UTC period.');
      const created = object(
        await atlasApi.createExperiment({
          strategyVersionId: strategy,
          datasetSnapshotId: snapshot,
          tradingStart,
          tradingEnd,
          startingCapital: capital,
          riskPerTrade: risk,
          parameters: Object.fromEntries(
            schema.map((descriptor) => {
              const item = object(descriptor);
              const key = text(item.key, '');
              return [
                key,
                text(item.type) === 'integer'
                  ? Number(parameters[key])
                  : parameters[key],
              ];
            }),
          ),
          slippageTicks: Number(slippage),
          commissionPerUnit: commission,
        }),
      );
      router.push(`/experiments/${text(created.id)}?start=1`);
    } catch (error) {
      setFormError(errorMessage(error));
      setSubmitting(false);
    }
  };
  const blocking = Array.isArray(coverage?.blockingReasons)
    ? coverage.blockingReasons
    : [];
  const selectedSnapshot = object(
    snapshots.find((value) => text(object(value).id, '') === snapshot) ??
      object(historicalLoad?.snapshot),
  );
  const selectedSnapshotIntegrity = object(selectedSnapshot.integrity);
  const snapshotSelectionBlocked = Boolean(
    snapshot && snapshotOptionState(selectedSnapshot, snapshots).disabled,
  );
  const snapshotOptions = snapshots.map((value) => {
    const item = object(value);
    return { item, ...snapshotOptionState(item, snapshots) };
  });
  const proofSource = object(historicalLoad?.source ?? capability);
  const proofFingerprint = text(selectedSnapshot.fingerprint, 'awaiting data');
  const proofStatus = historicalLoad
    ? text(historicalLoad.status, 'awaiting data')
    : capability?.available === true
      ? 'idle'
      : capability?.available === false
        ? 'unavailable'
        : 'awaiting data';
  const proofLine = `Proof: ${text(proofSource.provider, 'provider unavailable')} ${text(proofSource.instrument, 'instrument unavailable')} · native M15 MID + sparse M1 BID/ASK → immutable snapshot ${proofFingerprint === 'awaiting data' ? proofFingerprint : proofFingerprint.slice(0, 8)} · load ${proofStatus}`;
  return (
    <AppShell>
      <section
        aria-labelledby="new-experiment-heading"
        className="flex max-w-4xl flex-col gap-8"
      >
        <header>
          <Link
            href="/experiments"
            className="mb-5 inline-flex items-center gap-2 text-sm text-atlas-foreground-muted hover:text-atlas-foreground"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Experiments
          </Link>
          <h1
            id="new-experiment-heading"
            className="text-3xl font-semibold tracking-tight"
          >
            New Experiment
          </h1>
          <p className="mt-2 text-sm text-atlas-foreground-muted">
            StrategyVersion → requested period &amp; data readiness →
            configuration → review &amp; run
          </p>
        </header>
        {Boolean(formError) && <ErrorPanel error={formError} />}
        <form onSubmit={submit} className="flex flex-col gap-6">
          <fieldset className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
            <legend className="px-1 text-base font-medium">
              1 · StrategyVersion
            </legend>
            <p className="max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
              Start with the immutable methodology snapshot that will be
              captured in the Experiment. Parameter changes belong to this run;
              they never mutate the StrategyVersion.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                StrategyVersion
                <Select
                  required
                  disabled={loadActive}
                  value={strategy}
                  onChange={(e) => {
                    const version = versions.find(
                      (value) => text(object(value).id) === e.target.value,
                    );
                    setStrategy(e.target.value);
                    setParameters(parameterDefaults(version));
                    invalidate();
                  }}
                  className="form-control"
                >
                  <option value="">Choose a StrategyVersion</option>
                  {versions.map((value) => {
                    const item = object(value);
                    return (
                      <option
                        key={text(item.id)}
                        value={text(item.id)}
                        disabled={item.executionAvailable === false}
                      >
                        {text(
                          item.displayName,
                          `${text(item.name, 'StrategyVersion')} · v${text(item.version)}`,
                        )}
                        {item.executionAvailable === false
                          ? ' · unavailable'
                          : ''}
                      </option>
                    );
                  })}
                </Select>
                {optionsLoading && strategy === '' && (
                  <span className="block text-xs font-normal text-atlas-foreground-muted">
                    Loading StrategyVersions…
                  </span>
                )}
              </label>
            </div>
            <div className="grid gap-4 border-t border-atlas-border pt-4 text-sm sm:grid-cols-3">
              <div>
                <p className="text-xs text-atlas-foreground-muted">Market</p>
                <p className="font-medium">
                  {text(
                    object(selectedVersion.marketRequirements).instrument,
                    'Unavailable from this StrategyVersion response',
                  )}
                </p>
              </div>
              <div>
                <p className="text-xs text-atlas-foreground-muted">Analysis</p>
                <p className="font-medium">
                  {text(
                    object(selectedVersion.marketRequirements).resolution,
                    text(
                      selectedVersion.timeframe,
                      'Unavailable from this StrategyVersion response',
                    ),
                  )}{' '}
                  {text(
                    object(selectedVersion.marketRequirements).priceComponent,
                    'Unavailable from this StrategyVersion response',
                  )}
                </p>
              </div>
              <div>
                <p className="text-xs text-atlas-foreground-muted">Warm-up</p>
                <p className="font-medium">
                  {Number.isFinite(requiredHistoricalContextBars)
                    ? `${requiredHistoricalContextBars} completed bars`
                    : 'Requirement unavailable'}
                </p>
              </div>
            </div>
            {selectedVersion.executionAvailable === false && (
              <p className="rounded-md border border-atlas-warning bg-atlas-warning-muted p-3 text-sm text-atlas-warning">
                This StrategyVersion is retained for provenance but cannot
                create a new Experiment.{' '}
                {text(selectedVersion.unavailableReason, '')}
              </p>
            )}
          </fieldset>
          <fieldset className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
            <legend className="px-1 text-base font-medium">
              2 · Requested period &amp; data readiness
            </legend>
            <p className="max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
              Choose the UTC trading window, then confirm native M15 MID and
              sparse M1 BID/ASK coverage before configuring the run.
            </p>
            <label className="max-w-xl space-y-2 text-sm font-medium">
              DatasetSnapshot
              <Select
                required
                disabled={loadActive}
                value={snapshot}
                onChange={(e) => {
                  setSnapshot(e.target.value);
                  invalidate();
                }}
                className="form-control"
              >
                <option value="">Choose historical data</option>
                {snapshotOptions.map(({ item, label, disabled }) => (
                  <option
                    key={text(item.id)}
                    value={text(item.id)}
                    disabled={disabled}
                  >
                    {label}
                  </option>
                ))}
              </Select>
              {snapshotOptions.some(({ disabled }) => disabled) && (
                <span className="block text-xs font-normal text-atlas-warning">
                  Some snapshots are unavailable because their visible coverage
                  facts are identical. Choose an unambiguous snapshot before
                  validating or running.
                </span>
              )}
              <span className="block text-xs font-normal text-atlas-foreground-muted">
                Atlas captures the selected immutable snapshot in the
                Experiment.
              </span>
            </label>
            <section
              aria-labelledby="available-data-heading"
              className="rounded-md border border-atlas-border bg-atlas-surface-hover p-4 text-sm"
            >
              <h2 id="available-data-heading" className="font-medium">
                Data available
              </h2>
              <p className="mt-1 text-xs text-atlas-foreground-muted">
                Data coverage is checked for the selected Period.
              </p>
              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-medium">
                  Technical details
                </summary>
                <p className="mt-2 text-xs text-atlas-foreground-muted">
                  {proofLine}
                </p>
                <p className="mt-1 text-xs text-atlas-foreground-muted">
                  Policy:{' '}
                  {text(
                    selectedSnapshotIntegrity.policyVersion ??
                      selectedSnapshotIntegrity.policy_version ??
                      selectedSnapshotIntegrity.sessionPolicy ??
                      selectedSnapshotIntegrity.session_policy,
                    'ATLAS_HISTORICAL_GAP_POLICY_V1',
                  )}
                </p>
                <dl className="mt-3 grid gap-3 sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-atlas-foreground-muted">
                      Earliest native M15
                    </dt>
                    <dd className="font-medium">
                      {snapshots.length
                        ? formatInstant(
                            snapshots.reduce((a, b) =>
                              String(object(a).coverageStart) <
                              String(object(b).coverageStart)
                                ? a
                                : b,
                            ).coverageStart,
                            'UTC',
                          )
                        : 'Unknown'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-atlas-foreground-muted">
                      Latest native M15
                    </dt>
                    <dd className="font-medium">
                      {snapshots.length
                        ? formatInstant(
                            snapshots.reduce((a, b) =>
                              String(object(a).coverageEnd) >
                              String(object(b).coverageEnd)
                                ? a
                                : b,
                            ).coverageEnd,
                            'UTC',
                          )
                        : 'Unknown'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-atlas-foreground-muted">
                      Last snapshot
                    </dt>
                    <dd className="font-medium">
                      {snapshots.length
                        ? snapshotLabel(object(snapshots[snapshots.length - 1]))
                        : 'Unknown'}
                    </dd>
                  </div>
                </dl>
              </details>
              {inventoryLoading && (
                <p className="mt-3 text-xs text-atlas-foreground-muted">
                  Checking selected coverage…
                </p>
              )}
              {inventory &&
                !inventoryLoading &&
                Array.isArray(inventory.blockingReasons) &&
                inventory.blockingReasons.length > 0 &&
                snapshots.length > 0 && (
                  <p className="mt-3 text-xs text-atlas-foreground-muted">
                    Preview:{' '}
                    {inventory.blockingReasons.includes(
                      'INSUFFICIENT_WARMUP',
                    ) ||
                    inventory.blockingReasons.includes('RANGE_OUTSIDE_SNAPSHOT')
                      ? 'This period needs a load first — hit Load below to fetch the missing bars.'
                      : `Preview blocking: ${inventory.blockingReasons.map(String).join(' · ')}`}
                  </p>
                )}
              {inventory &&
                !inventoryLoading &&
                Array.isArray(inventory.blockingReasons) &&
                inventory.blockingReasons.length === 0 &&
                snapshots.length > 0 && (
                  <p className="mt-3 text-xs text-atlas-positive">
                    Preview: this period looks ready to validate.
                  </p>
                )}
            </section>
            <div className="grid gap-4 md:grid-cols-2">
              <UtcDateTimePicker
                label="Trading start"
                value={dateInput(start)}
                disabled={loadActive}
                onChange={(value) => {
                  setStart(value);
                  invalidate();
                }}
              />
              <UtcDateTimePicker
                label="Trading end"
                value={dateInput(end)}
                disabled={loadActive}
                onChange={(value) => {
                  setEnd(value);
                  invalidate();
                }}
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-atlas-foreground-muted">
                Presets
              </span>
              {(['1W', '1M', '3M'] as const).map((preset) => (
                <Button
                  key={preset}
                  type="button"
                  className="min-h-8 px-3 text-xs"
                  title={
                    !strategyReady ? 'Pick a StrategyVersion first' : undefined
                  }
                  disabled={!strategyReady || loadActive}
                  onClick={() => applyPreset(preset)}
                >
                  {preset}
                </Button>
              ))}
            </div>
            <details className="rounded-md border border-atlas-border bg-atlas-surface-hover p-4 text-sm">
              <summary className="cursor-pointer font-medium">
                Technical details
              </summary>
              <div className="mt-2">
                <p>
                  Load range{' '}
                  <span className="font-normal">[{loadRangeLabel})</span>
                </p>
                <p className="mt-1">
                  {loadDurationDays === null
                    ? 'Enter valid UTC times to preview duration.'
                    : `${loadDurationDays.toFixed(1)} days · includes ${Number.isFinite(requiredHistoricalContextBars) ? requiredHistoricalContextBars : 'unknown'} required M15 context bars`}
                </p>
                <p className="mt-1 text-xs">
                  Constraints: ≤90 days · ≤40 missing windows (server preflight)
                </p>
                {loadRangeTooLarge && (
                  <p className="mt-2 font-medium">
                    Product validation: shorten the period so the
                    required-context-inclusive load range is 90 days or less.
                  </p>
                )}
              </div>
            </details>
            {snapshots.length === 0 && (
              <div className="rounded-md border border-atlas-warning bg-atlas-warning-muted p-4 text-sm text-atlas-warning">
                <p className="font-medium">
                  No data yet — load your first month below
                </p>
                <p className="mt-1 text-xs">
                  Pick a period like{' '}
                  <span className="font-mono">2024-01-01 → 2024-02-01</span>,
                  then load the available market data.
                </p>
              </div>
            )}
          </fieldset>
          <div className="rounded-lg border border-atlas-border bg-atlas-surface p-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="inline-flex items-center gap-1 rounded-full bg-atlas-positive-muted px-3 py-1 text-xs font-medium text-atlas-positive">
                {strategyReady
                  ? '1. StrategyVersion selected'
                  : '1. Select StrategyVersion'}
              </span>
              <span aria-hidden className="text-atlas-foreground-disabled">
                →
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-atlas-primary-muted px-3 py-1 text-xs font-medium text-atlas-primary">
                2. Period &amp; data readiness
              </span>
              <span aria-hidden className="text-atlas-foreground-disabled">
                →
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-atlas-surface-selected px-3 py-1 text-xs font-medium text-atlas-foreground-muted">
                3. Configuration
              </span>
              <span aria-hidden className="text-atlas-foreground-disabled">
                →
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${coverage?.valid && !loadBlocksCreation ? 'bg-atlas-positive-muted text-atlas-positive' : 'bg-atlas-surface-selected text-atlas-foreground-muted'}`}
              >
                4. Review &amp; run
              </span>
            </div>
            <p className="mt-2 text-xs text-atlas-foreground-muted">
              Loading continues durably. You can close this tab; return to
              review the status before running.
            </p>
          </div>
          {status === 'COMPLETED' && (
            <div
              role="status"
              aria-live="polite"
              className="rounded-lg border border-atlas-positive bg-atlas-positive-muted p-4 text-sm text-atlas-positive"
            >
              <p className="font-semibold">
                ✓ Ready — {dateLabel(historicalLoad?.tradingStart, 'UTC')} →{' '}
                {dateLabel(historicalLoad?.tradingEnd, 'UTC')}
              </p>
              <p className="mt-1">
                {text(
                  object(historicalLoad?.snapshot) &&
                    snapshotLabel(object(object(historicalLoad?.snapshot))),
                  text(historicalLoad?.displayLabel, 'Snapshot selected'),
                )}{' '}
                — coverage re-validated. Hit{' '}
                <span className="font-semibold">Run Experiment</span> below.
              </p>
            </div>
          )}
          <section
            aria-live="polite"
            className="rounded-lg border border-atlas-primary bg-atlas-primary-muted p-5 text-sm text-atlas-primary"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-medium">Historical data coverage</h2>
                <details className="mt-3 text-xs">
                  <summary className="cursor-pointer font-medium">
                    Technical details
                  </summary>
                  <p className="mt-2">
                    UTC wall-clock entry. Display timezone only changes labels,
                    never the request.
                  </p>
                </details>
                {capability?.available === false && (
                  <p className="mt-2 font-medium">
                    Historical loading is unavailable on this server.
                  </p>
                )}
                {historicalLoad && (
                  <>
                    <p className="mt-2 flex flex-wrap items-center gap-2">
                      <span>{text(historicalLoad.displayLabel)}</span>
                      <StatusBadge status={statusOf(historicalLoad.status)} />
                      {(status === 'PENDING' || status === 'RUNNING') && (
                        <span className="inline-flex items-center gap-1 text-xs">
                          <LoaderCircle
                            className="size-3 animate-spin"
                            aria-hidden
                          />{' '}
                          Loading market data and validating strategy coverage.
                        </span>
                      )}
                    </p>
                    <details className="mt-3 text-xs">
                      <summary className="cursor-pointer font-medium">
                        Technical details
                      </summary>
                      <dl className="mt-3 grid gap-3 sm:grid-cols-3">
                        <div>
                          <dt className="text-atlas-primary/70">
                            Fetched ranges
                          </dt>
                          <dd className="font-medium">
                            {Array.isArray(progress.fetchedRanges)
                              ? progress.fetchedRanges.length
                              : 'Unknown'}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-atlas-primary/70">
                            Committed ranges
                          </dt>
                          <dd className="font-medium">
                            {Array.isArray(progress.committedRanges)
                              ? progress.committedRanges.length
                              : 'Unknown'}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-atlas-primary/70">
                            Member minutes
                          </dt>
                          <dd className="font-medium">
                            {text(loadCoverage.memberMinutes, 'Unknown')}
                          </dd>
                        </div>
                      </dl>
                      <p className="mt-2">
                        Inserted {text(progress.inserted, 'Unknown')} ·
                        Reactivated {text(progress.reactivated, 'Unknown')} ·
                        Unchanged {text(progress.unchanged, 'Unknown')}
                      </p>
                    </details>
                    {visibleDiagnostics(loadCoverage).length > 0 && (
                      <ul className="mt-2 list-disc pl-5 text-xs">
                        {visibleDiagnostics(loadCoverage).map((item, index) => (
                          <li key={index}>{diagnosticLabel(item)}</li>
                        ))}
                      </ul>
                    )}
                    <p className="mt-2 text-xs font-medium">
                      Loading market data and validating strategy coverage.
                    </p>
                    {(() => {
                      const completed = Number(progress.completedUnits);
                      const total = Number(progress.totalUnits);
                      const determinate =
                        Number.isFinite(completed) &&
                        Number.isFinite(total) &&
                        total > 0;
                      const percent = determinate
                        ? Math.min(100, Math.max(0, (completed / total) * 100))
                        : 0;
                      return (
                        <div
                          className="mt-3"
                          aria-label={
                            determinate
                              ? `Data preparation ${percent.toFixed(0)}% complete`
                              : 'Data preparation in progress'
                          }
                        >
                          <div className="h-2 overflow-hidden rounded-full bg-atlas-primary-muted">
                            <div
                              className={`h-full bg-atlas-primary ${determinate ? '' : 'w-1/3 animate-pulse'}`}
                              style={
                                determinate
                                  ? { width: `${percent}%` }
                                  : undefined
                              }
                            />
                          </div>
                          <p className="mt-1 text-xs">
                            {determinate
                              ? `${completed} of ${total} work units complete`
                              : 'Progress is being recorded as work completes.'}
                          </p>
                        </div>
                      );
                    })()}
                    <p className="mt-1 text-xs">
                      Load status is durable; Atlas will not restart an
                      uncertain command.
                    </p>
                    <p className="mt-1 text-xs">
                      Committed progress is saved; Atlas will not restart the
                      command automatically.
                    </p>
                  </>
                )}
                {Boolean(historicalLoad?.failure) && (
                  <p className="mt-1">
                    Load failed. Valid partial bars may remain. Start a new load
                    after reviewing coverage.
                  </p>
                )}
                {pollFailures >= 3 && (
                  <p className="mt-1 font-medium">
                    Status is unknown. Atlas did not resend the load.
                  </p>
                )}
                {Boolean(loadMessage) && (
                  <div className="mt-3">
                    <ErrorPanel error={loadMessage} />
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                {pollFailures >= 3 && (
                  <Button
                    type="button"
                    onClick={() => {
                      setPollFailures(0);
                      setPollPaused(false);
                    }}
                  >
                    Resume status check
                  </Button>
                )}
                <Button
                  type="button"
                  title={
                    !strategyReady ? 'Pick a StrategyVersion first' : undefined
                  }
                  onClick={loadHistoricalData}
                  disabled={
                    !strategyReady ||
                    !start ||
                    !end ||
                    loadRangeTooLarge ||
                    capability?.available === false ||
                    ['PENDING', 'RUNNING'].includes(
                      text(historicalLoad?.status, ''),
                    )
                  }
                >
                  Load missing historical data
                </Button>
              </div>
            </div>
          </section>
          <fieldset className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
            <legend className="px-1 text-base font-medium">
              3 · Strategy &amp; risk configuration
            </legend>
            <p className="max-w-2xl text-sm leading-6 text-atlas-foreground-muted">
              Values are captured in this Experiment only. Enter a value within
              the bounds defined by the selected StrategyVersion.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              {schema.map((value) => {
                const descriptor = object(value);
                const key = text(descriptor.key, '');
                const fixed = Number(descriptor.min) === Number(descriptor.max);
                const error = text(parameterErrors[key], '');
                return (
                  <label key={key} className="space-y-2 text-sm font-medium">
                    <span className="block">{text(descriptor.label, key)}</span>
                    <input
                      aria-describedby={`${key}-hint ${key}-error`}
                      aria-invalid={Boolean(error)}
                      className={`form-control ${fixed ? 'bg-atlas-surface-hover text-atlas-foreground-muted' : ''}`}
                      inputMode={
                        text(descriptor.type) === 'integer'
                          ? 'numeric'
                          : 'decimal'
                      }
                      readOnly={fixed}
                      type="text"
                      value={parameters[key] ?? ''}
                      onChange={(event) => {
                        setParameters((current) => ({
                          ...current,
                          [key]: event.target.value,
                        }));
                        invalidate();
                      }}
                    />
                    <span
                      id={`${key}-hint`}
                      className="block text-xs font-normal text-atlas-foreground-muted"
                    >
                      {fixed
                        ? 'Fixed by methodology.'
                        : `${text(descriptor.type)} · ${text(descriptor.min)} to ${text(descriptor.max)}`}
                      {text(descriptor.description, '')
                        ? ` · ${text(descriptor.description, '')}`
                        : ''}
                    </span>
                    {error && (
                      <span
                        id={`${key}-error`}
                        className="block text-xs font-normal text-atlas-negative"
                      >
                        {error}
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          </fieldset>
          <fieldset className="flex flex-col gap-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
            <legend className="px-1 text-base font-medium">
              Account &amp; risk configuration
            </legend>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                Starting capital
                <input
                  required
                  min="1"
                  step="0.01"
                  value={capital}
                  onChange={(e) => {
                    setCapital(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="decimal"
                />
              </label>
              <label className="space-y-2 text-sm font-medium">
                Risk per trade
                <input
                  required
                  min="0.0001"
                  max="1"
                  step="0.0001"
                  value={risk}
                  onChange={(e) => {
                    setRisk(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="decimal"
                />
              </label>
            </div>
          </fieldset>
          <fieldset className="space-y-4 rounded-lg border border-atlas-border bg-atlas-surface p-5">
            <legend className="px-1 text-base font-medium">
              Simulation costs
            </legend>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                Adverse slippage (ticks)
                <input
                  required
                  min="0"
                  step="1"
                  value={slippage}
                  onChange={(e) => {
                    setSlippage(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="numeric"
                />
              </label>
              <label className="space-y-2 text-sm font-medium">
                Commission per unit (USD)
                <input
                  required
                  min="0"
                  step="0.0001"
                  value={commission}
                  onChange={(e) => {
                    setCommission(e.target.value);
                    invalidate();
                  }}
                  className="form-control"
                  inputMode="decimal"
                />
              </label>
            </div>
            <details className="text-xs text-atlas-foreground-muted">
              <summary className="cursor-pointer font-medium">
                Technical details
              </summary>
              <p className="mt-2">
                Native M15 MID analysis · sparse M1 BID/ASK execution · entry
                only in the immediately following one-minute bucket · Financing
                excluded
              </p>
            </details>
          </fieldset>
          <section
            aria-live="polite"
            className={`rounded-lg border p-5 ${coverage ? (coverage.valid ? 'border-atlas-positive bg-atlas-positive-muted' : 'border-atlas-warning bg-atlas-warning-muted') : 'border-atlas-border bg-atlas-surface-hover'}`}
          >
            <div className="flex items-start gap-3">
              <CheckCircle2
                className="mt-0.5 size-5 shrink-0 text-atlas-positive"
                aria-hidden
              />
              <div>
                <h2 className="font-medium">4 · Review &amp; run Experiment</h2>
                <p className="mt-1 text-xs text-atlas-foreground-muted">
                  Coverage is the final gate. Atlas will capture these immutable
                  inputs only after the selected period validates successfully.
                </p>
                <dl className="mt-4 grid gap-3 border-y border-atlas-border py-3 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-atlas-foreground-muted">
                      StrategyVersion
                    </dt>
                    <dd className="font-medium">
                      {text(selectedVersion.displayName, 'Not selected')}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-atlas-foreground-muted">
                      Requested period
                    </dt>
                    <dd className="font-medium">
                      {start && end
                        ? `${dateLabel(iso(start), 'UTC')} → ${dateLabel(iso(end), 'UTC')}`
                        : 'Not selected'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-atlas-foreground-muted">
                      DatasetSnapshot
                    </dt>
                    <dd className="font-medium">
                      {snapshot
                        ? snapshotLabel(selectedSnapshot)
                        : 'Not selected'}
                    </dd>
                  </div>
                </dl>
                <h3 className="mt-4 font-medium">Coverage validation</h3>
                {!coverage ? (
                  <p className="mt-1 text-sm text-atlas-foreground-muted">
                    Validate the selected period to check required historical
                    context and immutable V2 snapshot coverage.
                  </p>
                ) : (
                  <>
                    <p className="mt-1 text-sm">
                      {coverage.valid
                        ? 'The selected period is eligible to run.'
                        : 'This period cannot run yet.'}
                    </p>
                    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                      <div>
                        <dt className="text-atlas-foreground-muted">
                          Historical context
                        </dt>
                        <dd className="font-medium">
                          {text(object(coverage.historicalContext).available)} /{' '}
                          {text(object(coverage.historicalContext).required)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-atlas-foreground-muted">
                          Open minutes
                        </dt>
                        <dd className="font-medium">
                          {text(object(coverage.counts).memberMinutes)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-atlas-foreground-muted">Gaps</dt>
                        <dd className="font-medium">
                          {Array.isArray(coverage.gaps)
                            ? coverage.gaps.length
                            : 0}
                        </dd>
                      </div>
                    </dl>
                    {blocking.length > 0 && (
                      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm">
                        {blocking.map((reason) => (
                          <li key={String(reason)}>{String(reason)}</li>
                        ))}
                      </ul>
                    )}
                    {visibleDiagnostics(coverage).length > 0 && (
                      <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-atlas-warning">
                        {visibleDiagnostics(coverage).map((item, index) => (
                          <li key={index}>{diagnosticLabel(item)}</li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            </div>
          </section>
          <div className="flex flex-wrap justify-end gap-3">
            <Button
              type="button"
              onClick={() => void validate()}
              disabled={
                validating ||
                !strategy ||
                !snapshot ||
                snapshotSelectionBlocked ||
                !start ||
                !end ||
                ['PENDING', 'RUNNING'].includes(
                  text(historicalLoad?.status, ''),
                )
              }
            >
              {validating && (
                <LoaderCircle
                  className="mr-2 size-4 animate-spin"
                  aria-hidden
                />
              )}
              Validate coverage
            </Button>
            <Button
              type="submit"
              title={
                !coverage?.valid
                  ? 'Validate coverage first'
                  : snapshotSelectionBlocked
                    ? 'This snapshot cannot be selected because its visible facts are ambiguous'
                    : loadBlocksCreation
                      ? 'Historical load must complete successfully first'
                      : undefined
              }
              className={
                coverage?.valid && !loadBlocksCreation && !submitting
                  ? 'animate-pulse shadow-lg'
                  : undefined
              }
              disabled={
                submitting ||
                !coverage?.valid ||
                loadBlocksCreation ||
                snapshotSelectionBlocked ||
                selectedVersion.executionAvailable === false ||
                Object.keys(parameterErrors).length > 0
              }
            >
              {submitting && (
                <LoaderCircle
                  className="mr-2 size-4 animate-spin"
                  aria-hidden
                />
              )}
              Run Experiment
            </Button>
          </div>
        </form>
      </section>
    </AppShell>
  );
}
