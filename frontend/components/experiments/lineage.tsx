'use client';

import {
  dateLabel,
  object,
  priceLabel,
  text,
  moneyLabel,
  rLabel,
} from './shared';
import type { Json } from './shared';
import type { DisplayTimeZone } from '../../lib/time';
import type { ReactNode } from 'react';

const labels: Record<string, string> = {
  atr: 'ATR',
  close: 'Close',
  confirmation: 'Confirmation candle',
  entry_policy: 'Entry policy',
  entryPolicy: 'Entry policy',
  entry_price: 'Entry price',
  event_type: 'Event',
  expiry_bars: 'Expiry bars',
  executed_at: 'Executed',
  execution_price: 'Execution price',
  fee: 'Fee',
  high: 'High',
  low: 'Low',
  net_pnl: 'Net P&L',
  opened_at: 'Opened',
  order_type: 'Order type',
  outcome: 'Outcome',
  phase: 'Risk phase',
  proposalStatus: 'Proposal status',
  quantity: 'Quantity',
  rejection_code: 'Rejection reason',
  reference: 'Reference candle',
  risk_budget: 'Risk budget',
  r_multiple: 'R multiple',
  stop_methodology: 'Stop methodology',
  stop_price: 'Stop price',
  sweep: 'Sweep candle',
  target_price: 'Target price',
  trend_relation: 'Trend relation',
  trigger_price: 'Trigger price',
  triggerPrice: 'Trigger price',
  trigger_price_basis: 'Trigger price basis',
  triggerPriceBasis: 'Trigger price basis',
  current_status: 'Status',
  purpose: 'Purpose',
};

const humanLabel = (key: string) =>
  labels[key] ??
  key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replaceAll('_', ' ')
    .replace(/^./, (value) => value.toUpperCase());

const hiddenKey = (key: string) =>
  key.toLowerCase().endsWith('id') ||
  key.toLowerCase().includes('fingerprint') ||
  key.toLowerCase().includes('implementation') ||
  key.toLowerCase().includes('source_');

const isDateKey = (key: string) =>
  key === 't' || key.endsWith('_at') || key === 'time' || key === 'timestamp';

const isPriceKey = (key: string) =>
  key.includes('price') ||
  key === 'open' ||
  key === 'high' ||
  key === 'low' ||
  key === 'close';

const formatValue = (
  key: string,
  value: unknown,
  timeZone?: DisplayTimeZone,
) => {
  if (value === null || value === undefined || value === '') return '—';
  if (isDateKey(key)) return dateLabel(value, timeZone);
  if (isPriceKey(key)) return priceLabel(value);
  if (key.includes('pnl') || key === 'fee' || key === 'risk_budget') {
    return moneyLabel(value);
  }
  if (key === 'r_multiple') return rLabel(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'string' || typeof value === 'number')
    return String(value);
  return 'Recorded details';
};

function Rows({
  value,
  timeZone,
}: {
  value: unknown;
  timeZone?: DisplayTimeZone;
}) {
  const entries = Object.entries(object(value)).filter(
    ([key, item]) =>
      !hiddenKey(key) && item !== undefined && typeof item !== 'object',
  );
  if (!entries.length)
    return (
      <p className="text-sm text-atlas-foreground-muted">
        No additional recorded details.
      </p>
    );
  return (
    <dl className="grid gap-x-5 gap-y-3 sm:grid-cols-2">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt className="text-xs text-atlas-foreground-muted">
            {humanLabel(key)}
          </dt>
          <dd className="break-words text-sm">
            {formatValue(key, item, timeZone)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Rationale({
  data,
  timeZone,
}: {
  data: Json;
  timeZone?: DisplayTimeZone;
}) {
  const rationale = object(data.rationale);
  const fields = rationale.fields;
  const pairs = Array.isArray(fields)
    ? fields.filter(
        (item): item is [string, unknown] =>
          Array.isArray(item) && typeof item[0] === 'string',
      )
    : Object.entries(object(fields));
  return pairs.length ? (
    <dl className="grid gap-x-5 gap-y-3 sm:grid-cols-2">
      {pairs
        .filter(([key]) => !hiddenKey(key) && key !== 'setup_facts')
        .map(([key, value]) => (
          <div key={key}>
            <dt className="text-xs text-atlas-foreground-muted">
              {humanLabel(key)}
            </dt>
            <dd className="break-words text-sm">
              {formatValue(key, value, timeZone)}
            </dd>
          </div>
        ))}
    </dl>
  ) : (
    <p className="text-sm text-atlas-foreground-muted">
      No separate rationale fields were recorded for this Trade.
    </p>
  );
}

function SetupFacts({
  data,
  timeZone,
}: {
  data: Json;
  timeZone?: DisplayTimeZone;
}) {
  const setup = object(data.setupFacts);
  const stages = ['reference', 'sweep', 'confirmation'].filter(
    (stage) => Object.keys(object(setup[stage])).length > 0,
  );
  return (
    <div className="flex flex-col gap-4">
      {stages.length > 0 && (
        <div className="grid gap-3 md:grid-cols-3">
          {stages.map((stage) => (
            <div
              key={stage}
              className="rounded-md border border-atlas-border bg-atlas-surface p-3"
            >
              <h4 className="text-sm font-medium">{humanLabel(stage)}</h4>
              <div className="mt-3">
                <Rows value={setup[stage]} timeZone={timeZone} />
              </div>
            </div>
          ))}
        </div>
      )}
      <Rows value={setup} timeZone={timeZone} />
    </div>
  );
}

function RiskDecisions({
  data,
  timeZone,
}: {
  data: Json;
  timeZone?: DisplayTimeZone;
}) {
  const risks = Array.isArray(data.risks) ? data.risks : [];
  if (!risks.length)
    return (
      <p className="text-sm text-atlas-foreground-muted">
        No Risk decisions were recorded.
      </p>
    );
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {risks.map((risk, index) => (
        <div
          key={index}
          className="rounded-md border border-atlas-border bg-atlas-surface p-3"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h4 className="text-sm font-medium">
              {text(object(risk).phase, 'Risk decision')}
            </h4>
            <span className="text-sm">{text(object(risk).outcome)}</span>
          </div>
          <div className="mt-3">
            <Rows value={risk} timeZone={timeZone} />
          </div>
        </div>
      ))}
    </div>
  );
}

function ExecutionLineage({
  data,
  timeZone,
}: {
  data: Json;
  timeZone?: DisplayTimeZone;
}) {
  const rawOrders = Array.isArray(data.orders) ? data.orders : [];
  const orders = rawOrders.map((raw) => {
    if (Array.isArray(raw))
      return {
        order: object(raw[0]),
        events: Array.isArray(raw[1]) ? raw[1] : [],
      };
    const order = object(raw);
    return { order, events: Array.isArray(order.events) ? order.events : [] };
  });
  const fills = Array.isArray(data.fills) ? data.fills : [];
  return (
    <section
      aria-labelledby="order-fill-heading"
      className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4"
    >
      <h2 id="order-fill-heading" className="font-medium">
        Order and Fill
      </h2>
      <p className="mt-1 text-sm text-atlas-foreground-muted">
        Recorded execution facts for this Trade. Detailed events remain
        available without crowding the normal reading path.
      </p>
      <details className="mt-4 rounded-lg border border-atlas-border bg-atlas-surface p-4">
        <summary className="cursor-pointer font-medium">
          Execution lineage
        </summary>
        <div className="mt-5 flex flex-col gap-5">
          <section>
            <h4 className="text-sm font-medium">Orders and events</h4>
            {orders.length ? (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {orders.map(({ order, events }, index) => (
                  <div
                    key={index}
                    className="rounded-md border border-atlas-border bg-atlas-surface p-3"
                  >
                    <h5 className="text-sm font-medium">
                      {text(order.purpose, `Order ${index + 1}`)}
                    </h5>
                    <div className="mt-3">
                      <Rows value={order} timeZone={timeZone} />
                    </div>
                    {events.length > 0 && (
                      <ul className="mt-3 flex flex-col gap-2 border-t border-atlas-border pt-3 text-xs text-atlas-foreground-muted">
                        {events.map((event, eventIndex) => {
                          const item = object(event);
                          return (
                            <li key={eventIndex}>
                              {text(item.event_type, 'Order event')} ·{' '}
                              {dateLabel(item.occurred_at, timeZone)}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-atlas-foreground-muted">
                No Orders were recorded.
              </p>
            )}
          </section>
          <section>
            <h4 className="text-sm font-medium">Fills</h4>
            {fills.length ? (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {fills.map((fill, index) => (
                  <div
                    key={index}
                    className="rounded-md border border-atlas-border bg-atlas-surface p-3"
                  >
                    <h5 className="text-sm font-medium">Fill {index + 1}</h5>
                    <div className="mt-3">
                      <Rows value={fill} timeZone={timeZone} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-atlas-foreground-muted">
                No Fills were recorded.
              </p>
            )}
          </section>
        </div>
      </details>
    </section>
  );
}

export function Lineage({
  data,
  context,
}: {
  data: Json;
  context?: ReactNode;
}) {
  // The API supplies this evidence at decision time. The UI only labels and
  // arranges those persisted facts; it does not detect a setup itself.
  return (
    <div className="flex flex-col gap-5">
      <section
        aria-labelledby="strategy-evidence-heading"
        className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4"
      >
        <h2 id="strategy-evidence-heading" className="font-medium">
          Strategy evidence
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Persisted evidence captured with the TradeIntent.
        </p>
        <h3 className="mt-4 text-sm font-medium">Why this Trade happened</h3>
        <h3 className="mt-2 text-sm font-medium">TradeIntent rationale</h3>
        <div className="mt-3">
          <Rationale data={data} />
        </div>
        {Boolean(data.setupFacts) && (
          <>
            <h3 className="mt-5 text-sm font-medium">Setup facts</h3>
            <div className="mt-3">
              <SetupFacts data={data} />
            </div>
          </>
        )}
        {context}
      </section>
      <section
        aria-labelledby="risk-decision-heading"
        className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4"
      >
        <h2 id="risk-decision-heading" className="font-medium">
          Risk decision
        </h2>
        <p className="mt-1 text-sm text-atlas-foreground-muted">
          Recorded Risk evaluation for this TradeIntent.
        </p>
        <div className="mt-3">
          <RiskDecisions data={data} />
        </div>
      </section>
      <ExecutionLineage data={data} />
    </div>
  );
}
