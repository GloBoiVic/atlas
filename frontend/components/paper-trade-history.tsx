'use client';

import { useCallback } from 'react';
import type { components } from '../lib/api.generated';
import { useDisplayTimeZone } from '../app/providers';
import { formatMoney, formatPrice } from '../lib/experiment-formatters';
import { formatInstrumentDisplay } from '../lib/instrument';
import { formatInstant } from '../lib/time';
import { atlasApi } from '../lib/api-client';
import { EmptyState, LoadingState, useReadResource } from './read-resource';

type PaperTrade = components['schemas']['PaperTradeHistoryItemResponse'];
type PaperTradeHistory = components['schemas']['PaperTradeHistoryResponse'];

const EXIT_CAUSE_LABELS: Record<string, string> = {
  TAKE_PROFIT: 'Target hit',
  STOP_LOSS: 'Stopped out',
  MARKET_CLOSE: 'Market close',
  MARGIN_CLOSEOUT: 'Margin closeout',
  OTHER: 'Other broker close',
};

function exitCauseLabel(cause: string | null): string {
  return (cause && EXIT_CAUSE_LABELS[cause]) ?? 'Exit cause unavailable';
}

function formatUnits(units: string, whole = false): string {
  const normalized =
    units.startsWith('-') || units.startsWith('+') ? units.slice(1) : units;
  const [integerPart, fractionalPart] = normalized.split('.');
  const grouped = (integerPart.replace(/^0+(?=\d)/, '') || '0').replace(
    /\B(?=(\d{3})+(?!\d))/g,
    ',',
  );
  return whole || fractionalPart === undefined
    ? grouped
    : `${grouped}.${fractionalPart}`;
}

function formatCompactInstrument(instrument: string): string {
  const normalized = formatInstrumentDisplay(instrument);
  return /^[A-Za-z]{6}$/.test(normalized)
    ? `${normalized.slice(0, 3)}/${normalized.slice(3)}`
    : normalized;
}

function formatCompactTime(
  value: string,
  timeZone: Parameters<typeof formatInstant>[1],
): string {
  const date = new Date(value);
  if (!Number.isFinite(date.valueOf())) return formatInstant(value, timeZone);

  return new Intl.DateTimeFormat('en-US', {
    timeZone,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
    .format(date)
    .replace(/, | at /, ' · ');
}

function directionLabel(direction: string): string {
  return direction === 'LONG' || direction === 'SHORT'
    ? direction
    : 'Direction unavailable';
}

function moneyTone(value: string): string {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount === 0) {
    return 'text-atlas-foreground';
  }
  return amount > 0 ? 'text-atlas-positive' : 'text-atlas-negative';
}

function hasNonZeroAmount(value: string): boolean {
  const amount = Number(value);
  return Number.isFinite(amount) && amount !== 0;
}

function strategyLabel(trade: PaperTrade): string {
  return `${trade.strategyName} v${trade.strategyVersionNumber}`;
}

function priceLabel(value: string | null): string {
  return value === null ? '—' : formatPrice(value);
}

function HistoryFact({
  label,
  value,
  mono = false,
  valueClassName = '',
}: {
  label: string;
  value: string;
  mono?: boolean;
  valueClassName?: string;
}) {
  return (
    <div className="border-t border-atlas-border pt-3">
      <dt className="text-xs text-atlas-foreground-muted">{label}</dt>
      <dd
        className={`mt-1 text-sm font-medium ${mono ? 'font-mono' : ''} ${valueClassName}`}
      >
        {value}
      </dd>
    </div>
  );
}

function CompactPriceFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-atlas-foreground-muted">{label}</dt>
      <dd className="mt-1 whitespace-nowrap font-mono text-sm font-medium">
        {value}
      </dd>
    </div>
  );
}

function CompactTrade({
  trade,
  timeZone,
}: {
  trade: PaperTrade;
  timeZone: Parameters<typeof formatInstant>[1];
}) {
  const realizedPl = formatMoney(trade.realizedPl);
  return (
    <li className="border-t border-atlas-border py-4 first:border-t-0 first:pt-0 last:pb-0">
      <article
        aria-label={`${formatCompactInstrument(trade.instrument)} ${directionLabel(trade.direction)} trade`}
        className="space-y-3"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-base font-semibold">
              <span>{formatCompactInstrument(trade.instrument)}</span>
              <span className="text-sm text-atlas-foreground-muted">
                {directionLabel(trade.direction)}
              </span>
            </p>
          </div>
          <p
            className={`shrink-0 text-lg font-semibold ${moneyTone(trade.realizedPl)}`}
          >
            <span className="sr-only">Realized P/L </span>
            {realizedPl}
          </p>
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm text-atlas-foreground-muted">
          <span>{strategyLabel(trade)}</span>
          <time dateTime={trade.closedAt}>
            {formatCompactTime(trade.closedAt, timeZone)}
          </time>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-y border-atlas-border py-3 sm:grid-cols-4">
          <CompactPriceFact
            label="Entry"
            value={priceLabel(trade.entryPrice)}
          />
          <CompactPriceFact
            label="Exit"
            value={priceLabel(trade.averageClosePrice)}
          />
          <CompactPriceFact label="Stop" value={priceLabel(trade.stopPrice)} />
          <CompactPriceFact
            label="Target"
            value={priceLabel(trade.targetPrice)}
          />
        </dl>
        <p className="text-xs text-atlas-foreground-muted">
          <span>{formatUnits(trade.units, true)} units</span>{' '}
          <span aria-hidden="true">·</span>{' '}
          <span>{exitCauseLabel(trade.exitCause)}</span>
        </p>
      </article>
    </li>
  );
}

function FullTrade({
  trade,
  timeZone,
}: {
  trade: PaperTrade;
  timeZone: Parameters<typeof formatInstant>[1];
}) {
  const exitCause = exitCauseLabel(trade.exitCause);
  return (
    <li>
      <article className="rounded border border-atlas-border p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-lg font-semibold">
              {formatInstrumentDisplay(trade.instrument)}{' '}
              <span className="text-atlas-foreground-muted">
                {directionLabel(trade.direction)}
              </span>
            </p>
            <p className="mt-1 text-sm text-atlas-foreground-muted">
              {strategyLabel(trade)} · {formatUnits(trade.units)} units
            </p>
          </div>
          <span className="status rounded-full border border-atlas-border bg-atlas-surface-hover px-2.5 py-1 text-atlas-foreground-muted">
            {exitCause}
          </span>
        </div>
        <dl className="mt-5 grid gap-x-6 gap-y-4 border-t border-atlas-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <HistoryFact
            label="Entry"
            value={priceLabel(trade.entryPrice)}
            mono
          />
          <HistoryFact
            label="Entered"
            value={formatInstant(trade.enteredAt, timeZone)}
          />
          <HistoryFact
            label="Exit"
            value={priceLabel(trade.averageClosePrice)}
            mono
          />
          <HistoryFact
            label="Closed"
            value={formatInstant(trade.closedAt, timeZone)}
          />
          <HistoryFact label="Stop" value={priceLabel(trade.stopPrice)} mono />
          <HistoryFact
            label="Target"
            value={priceLabel(trade.targetPrice)}
            mono
          />
          <HistoryFact
            label="Initial risk"
            value={formatMoney(trade.initialRisk)}
          />
          <HistoryFact
            label="Realized P/L"
            value={formatMoney(trade.realizedPl)}
            valueClassName={moneyTone(trade.realizedPl)}
          />
          <HistoryFact
            label="Financing"
            value={formatMoney(trade.financing)}
            valueClassName={moneyTone(trade.financing)}
          />
          {hasNonZeroAmount(trade.dividendAdjustment) && (
            <HistoryFact
              label="Dividend adjustment"
              value={formatMoney(trade.dividendAdjustment)}
              valueClassName={moneyTone(trade.dividendAdjustment)}
            />
          )}
        </dl>
      </article>
    </li>
  );
}

function HistoryReadError({ retry }: { retry: () => void }) {
  return (
    <div
      role="alert"
      className="space-y-3 border-l-2 border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
    >
      <p>Completed PAPER trades are unavailable.</p>
      <button
        type="button"
        onClick={retry}
        className="font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-focus-ring focus-visible:ring-offset-2"
      >
        Retry
      </button>
    </div>
  );
}

export function PaperTradeHistory({
  compact = false,
  limit = 10,
}: {
  compact?: boolean;
  limit?: number;
}) {
  const loader = useCallback(
    () => atlasApi.listPaperTrades({ limit }),
    [limit],
  );
  const { state, retry } = useReadResource<PaperTradeHistory>(loader);
  const { timeZone } = useDisplayTimeZone();
  const heading = compact ? 'Recent PAPER trades' : 'Completed PAPER trades';

  return (
    <section
      aria-labelledby={
        compact
          ? 'recent-paper-trades-heading'
          : 'completed-paper-trades-heading'
      }
      className="space-y-4"
    >
      <div>
        <h2
          id={
            compact
              ? 'recent-paper-trades-heading'
              : 'completed-paper-trades-heading'
          }
          className="text-lg font-semibold"
        >
          {heading}
        </h2>
        {!compact && (
          <p className="mt-1 text-sm text-atlas-foreground-muted">
            Durable outcomes from completed PAPER trades, separate from current
            broker and runtime state.
          </p>
        )}
      </div>
      {state.status === 'loading' && (
        <LoadingState
          label={compact ? 'recent PAPER trades' : 'completed PAPER trades'}
        />
      )}
      {state.status === 'error' && <HistoryReadError retry={retry} />}
      {state.status === 'ready' && state.data.items.length === 0 && (
        <EmptyState>No completed PAPER trades yet.</EmptyState>
      )}
      {state.status === 'ready' && state.data.items.length > 0 && (
        <ul className={compact ? 'space-y-0' : 'space-y-4'}>
          {state.data.items.map((trade, index) =>
            compact ? (
              <CompactTrade
                key={`${trade.closedAt}-${index}`}
                trade={trade}
                timeZone={timeZone}
              />
            ) : (
              <FullTrade
                key={`${trade.closedAt}-${index}`}
                trade={trade}
                timeZone={timeZone}
              />
            ),
          )}
        </ul>
      )}
    </section>
  );
}
