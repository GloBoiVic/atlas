'use client';

import { useCallback } from 'react';
import { atlasApi } from '../lib/api-client';
import { formatInstrumentDisplay } from '../lib/instrument';
import { formatInstant } from '../lib/time';
import { useDisplayTimeZone } from '../app/providers';
import {
  EmptyState,
  LoadingState,
  ReadError,
  UnavailableState,
  useReadResource,
} from './read-resource';
import type { components } from '../lib/api.generated';

type PaperBrokerState = components['schemas']['PaperBrokerStateResponse'];
type PaperBrokerTrade = components['schemas']['PaperBrokerTradeResponse'];

function formatUnitsAbsolute(units: string): string {
  const normalized =
    units.startsWith('-') || units.startsWith('+') ? units.slice(1) : units;
  // Keep decimal point handling without float conversion.
  const [intPart, fracPart] = normalized.split('.');
  const signlessInt = intPart.replace(/^0+(?=\d)/, '') || '0';
  const grouped = signlessInt.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return fracPart !== undefined ? `${grouped}.${fracPart}` : grouped;
}

function directionFromUnits(units: string): 'LONG' | 'SHORT' {
  return units.trim().startsWith('-') ? 'SHORT' : 'LONG';
}

function formatUnrealized(currency: string, value: string): string {
  const trimmed = value.trim();
  const negative = trimmed.startsWith('-');
  const abs = negative ? trimmed.slice(1) : trimmed.replace(/^[+]/, '');
  // Truncate for display without converting the provider value through a float.
  const [integerPart, fractionalPart] = abs.split('.');
  const absDisplay =
    fractionalPart === undefined
      ? abs
      : `${integerPart}.${fractionalPart.slice(0, 2)}`;
  // Prefix currency sensibly for USD, fallback to "value currency".
  if (currency === 'USD') {
    return `${negative ? '-' : ''}$${absDisplay}`;
  }
  return `${negative ? '-' : ''}${absDisplay} ${currency}`;
}

function unrealizedTone(value: string): 'positive' | 'negative' | 'neutral' {
  const trimmed = value.trim();
  const magnitude = trimmed.replace(/^[+-]/, '');
  const digits = magnitude.replace('.', '');

  if (!/^\d+(?:\.\d+)?$/.test(magnitude) || !digits || /^0+$/.test(digits)) {
    return 'neutral';
  }

  return trimmed.startsWith('-') ? 'negative' : 'positive';
}

function formatBrokerLabel(provider: string, environment: string): string {
  const environmentLabel =
    environment.trim().toUpperCase() === 'PRACTICE'
      ? 'Practice'
      : environment.trim();
  return [provider.trim(), environmentLabel].filter(Boolean).join(' ');
}

function BrokerTradeCard({
  trade,
  accountCurrency,
  timeZone,
  compact,
}: {
  trade: PaperBrokerTrade;
  accountCurrency: string;
  timeZone: string;
  compact: boolean;
}) {
  const direction = directionFromUnits(trade.currentUnits);
  const quantity = formatUnitsAbsolute(trade.currentUnits);
  const tone = unrealizedTone(trade.unrealizedPl);
  const toneClass =
    tone === 'negative'
      ? 'text-atlas-negative'
      : tone === 'positive'
        ? 'text-atlas-positive'
        : 'text-atlas-foreground';

  if (compact) {
    return (
      <div className="rounded border border-atlas-border p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-lg font-semibold">
              {formatInstrumentDisplay(trade.instrument)}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span
                className={`status rounded-full border px-2.5 py-1 text-xs ${
                  trade.state === 'OPEN'
                    ? 'border-atlas-positive bg-atlas-positive-muted text-atlas-positive'
                    : 'border-atlas-warning bg-atlas-warning-muted text-atlas-warning'
                }`}
              >
                {trade.state}
              </span>
              <span className="text-sm font-semibold">
                {direction}{' '}
                <span className="font-normal text-atlas-foreground-muted">
                  {quantity} units
                </span>
              </span>
            </div>
          </div>
        </div>
        <dl className="mt-5 border-t border-atlas-border pt-4">
          <dt className="text-xs text-atlas-foreground-muted">
            Unrealized P/L
          </dt>
          <dd className={`mt-1 text-2xl font-semibold ${toneClass}`}>
            {formatUnrealized(accountCurrency, trade.unrealizedPl)}
          </dd>
        </dl>
        <dl className="mt-4 grid gap-x-6 gap-y-3 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-atlas-foreground-muted">Entry</dt>
            <dd className="mt-1 text-sm font-mono">{trade.openPrice}</dd>
          </div>
          <div>
            <dt className="text-xs text-atlas-foreground-muted">Opened</dt>
            <dd className="mt-1 text-sm">
              {formatInstant(trade.openTime, timeZone as never)}
            </dd>
          </div>
        </dl>
      </div>
    );
  }

  return (
    <div className="rounded border border-atlas-border p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">
          {direction}{' '}
          <span className="font-normal text-atlas-foreground-muted">
            {quantity} units
          </span>
        </p>
        <span
          className={`status rounded-full border px-2.5 py-1 text-xs ${
            trade.state === 'OPEN'
              ? 'border-atlas-positive bg-atlas-positive-muted text-atlas-positive'
              : 'border-atlas-warning bg-atlas-warning-muted text-atlas-warning'
          }`}
        >
          {trade.state}
        </span>
      </div>
      <dl className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-atlas-foreground-muted">Instrument</dt>
          <dd className="mt-1 text-sm font-medium">
            {formatInstrumentDisplay(trade.instrument)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-atlas-foreground-muted">Entry</dt>
          <dd className="mt-1 text-sm font-mono">{trade.openPrice}</dd>
        </div>
        <div>
          <dt className="text-xs text-atlas-foreground-muted">
            Unrealized P/L
          </dt>
          <dd className={`mt-1 text-sm font-medium ${toneClass}`}>
            {formatUnrealized(accountCurrency, trade.unrealizedPl)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-atlas-foreground-muted">Opened</dt>
          <dd className="mt-1 text-sm">
            {formatInstant(trade.openTime, timeZone as never)}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs font-mono text-atlas-foreground-muted">
        Trade {trade.tradeId}
      </p>
    </div>
  );
}

export function PaperBrokerStateSection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const loader = useCallback(() => atlasApi.paperBrokerState(), []);
  const { state, retry } = useReadResource<PaperBrokerState>(loader);
  const { timeZone } = useDisplayTimeZone();

  return (
    <section aria-labelledby="paper-broker-state-heading" className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="paper-broker-state-heading" className="text-lg font-semibold">
            {compact ? 'Paper Trading' : 'PAPER broker state'}
          </h2>
          {!compact && (
            <p className="mt-1 text-sm text-atlas-foreground-muted">
              Current OANDA Practice open Trades. Broker exposure, not runtime.
            </p>
          )}
        </div>
        {state.status !== 'loading' && (
          <button
            type="button"
            onClick={retry}
            aria-label="Refresh broker state"
            className="rounded border border-atlas-border px-3 py-1.5 text-xs font-medium hover:bg-atlas-surface-hover"
          >
            Refresh
          </button>
        )}
      </div>

      {state.status === 'loading' && (
        <LoadingState
          label={compact ? 'broker exposure' : 'PAPER broker state'}
        />
      )}
      {state.status === 'error' &&
        (compact ? (
          <div className="space-y-3">
            <UnavailableState>Broker unavailable</UnavailableState>
            <button
              type="button"
              onClick={retry}
              className="text-sm font-medium text-atlas-primary underline-offset-2 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <ReadError error={state.error} retry={retry} />
            <UnavailableState>Broker unavailable</UnavailableState>
          </div>
        ))}
      {state.status === 'ready' && (
        <div className="space-y-4">
          <p className="text-sm text-atlas-foreground-muted">
            {formatBrokerLabel(state.data.provider, state.data.environment)}{' '}
            <span className="font-mono text-xs">
              {state.data.accountCurrency}
            </span>
          </p>
          {state.data.openTrades.length === 0 ? (
            <EmptyState>
              {compact ? 'No open trades' : 'No open broker trades.'}
            </EmptyState>
          ) : (
            <div className={compact ? 'space-y-3' : 'space-y-4'}>
              {state.data.openTrades.map((trade) => (
                <BrokerTradeCard
                  key={trade.tradeId}
                  trade={trade}
                  accountCurrency={state.data.accountCurrency}
                  timeZone={timeZone}
                  compact={compact}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// For overview compact variant, we keep less chrome but still include Refresh.
export function PaperBrokerStateCompact() {
  return <PaperBrokerStateSection compact />;
}
