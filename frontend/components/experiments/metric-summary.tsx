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

export function MetricSummary({
  label,
  value,
  format = 'number',
}: {
  label: string;
  value: unknown;
  format?: 'number' | 'percent' | 'money' | 'r';
}) {
  const data = metricState(value);
  const shown =
    data.state === 'VALUE'
      ? text(data.value)
      : data.state === 'INFINITE'
        ? '∞'
        : '—';
  const formatted =
    shown === '—' || shown === '∞'
      ? shown
      : format === 'money'
        ? moneyLabel(data.value)
        : format === 'percent'
          ? percentLabel(data.value)
          : format === 'r'
            ? rLabel(data.value)
            : shown;
  return (
    <div className="border-t border-atlas-border pt-3">
      <dt className="text-xs font-medium text-atlas-foreground-muted">
        {label}
      </dt>
      <dd
        className={`mt-1 text-lg font-semibold tabular-nums ${data.state === 'UNAVAILABLE' ? 'text-atlas-foreground-muted' : ''}`}
      >
        {formatted}
      </dd>
      {data.state !== 'VALUE' && data.state !== 'INFINITE' && (
        <p className="mt-1 text-xs text-atlas-foreground-muted">
          {text(data.reason, 'Not defined for this result')}
        </p>
      )}
    </div>
  );
}
