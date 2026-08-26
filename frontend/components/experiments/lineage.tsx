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
import {
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
  diagnosticLabel,
  formattedMetric,
  metricState,
  priceLabel,
  moneyLabel,
  rLabel,
  percentLabel,
} from './shared';

export function Lineage({ data }: { data: Json }) {
  const render = (value: unknown): React.ReactNode => {
    if (Array.isArray(value))
      return (
        <ul className="space-y-2">
          {value.map((item, index) => (
            <li
              key={index}
              className="rounded-md border border-atlas-border bg-atlas-surface p-3"
            >
              {render(item)}
            </li>
          ))}
        </ul>
      );
    if (value && typeof value === 'object')
      return (
        <dl className="grid gap-x-5 gap-y-2 sm:grid-cols-2">
          {Object.entries(value as Json)
            .filter(([key]) => !key.toLowerCase().endsWith('id'))
            .map(([key, item]) => (
              <div key={key}>
                <dt className="text-xs text-atlas-foreground-muted">
                  {key.replaceAll('_', ' ')}
                </dt>
                <dd className="break-words text-sm">{render(item)}</dd>
              </div>
            ))}
        </dl>
      );
    return <>{text(value)}</>;
  };
  return (
    <div className="space-y-3">
      <section className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4">
        <h3 className="font-medium">TradeIntent rationale</h3>
        <div className="mt-3">{render(data.rationale)}</div>
      </section>
      <section className="rounded-lg border border-atlas-border bg-atlas-surface-hover p-4">
        <h3 className="font-medium">Execution lineage</h3>
        <div className="mt-3 space-y-4">
          <div>
            <h4 className="text-sm font-medium">Risk decisions</h4>
            {render(data.risks)}
          </div>
          <div>
            <h4 className="text-sm font-medium">Orders and events</h4>
            {render(data.orders)}
          </div>
          <div>
            <h4 className="text-sm font-medium">Fills</h4>
            {render(data.fills)}
          </div>
        </div>
      </section>
    </div>
  );
}
