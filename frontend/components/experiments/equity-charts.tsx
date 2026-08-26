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

export function EquityChart({
  points,
  kind = 'equity',
}: {
  points: unknown[];
  kind?: 'equity' | 'drawdown';
}) {
  const { timeZone } = useDisplayTimeZone();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let chart: import('lightweight-charts').IChartApi | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({ createChart, LineSeries, ColorType }) => {
        // Lightweight Charts requires a real canvas; leave the host untouched
        // when a non-browser renderer cannot provide one (for example jsdom).
        // Test doubles remain usable because they expose no required arity.
        if (
          createChart.length > 0 &&
          typeof navigator !== 'undefined' &&
          navigator.userAgent.includes('jsdom')
        )
          return;
        if (!ref.current || disposed) return;
        chart = createChart(ref.current, {
          height: 260,
          width: Math.max(ref.current.clientWidth, 1),
          layout: {
            background: {
              type: ColorType.Solid,
              color: chartRoles.surface,
            },
            textColor: chartRoles.foregroundMuted,
          },
          grid: {
            vertLines: { color: chartRoles.border },
            horzLines: { color: chartRoles.border },
          },
          rightPriceScale: { borderColor: chartRoles.border },
          localization: {
            timeFormatter: (time: number) => formatChartTime(time, timeZone),
          },
          timeScale: {
            borderColor: chartRoles.border,
            tickMarkFormatter: (time: number) =>
              formatChartTick(time, timeZone),
          },
        });
        const series = chart.addSeries(LineSeries, {
          color: kind === 'drawdown' ? chartRoles.negative : chartRoles.primary,
          lineWidth: 2,
          priceLineVisible: false,
        });
        const data = points
          .map((raw) => {
            const item = object(raw);
            const date = new Date(text(item.observed_at, '')).getTime() / 1000;
            return {
              time: date as import('lightweight-charts').Time,
              value: Number(
                text(
                  item[kind === 'drawdown' ? 'drawdown_amount' : 'equity'],
                  '0',
                ),
              ),
            };
          })
          .filter(
            (item) => Number.isFinite(item.time) && Number.isFinite(item.value),
          );
        if (data.length) series.setData(strictlyAscending(data));
        chart.timeScale().fitContent();
        const observer = new ResizeObserver(() =>
          chart?.applyOptions({
            width: Math.max(ref.current?.clientWidth ?? 0, 1),
          }),
        );
        observer.observe(ref.current);
        (
          chart as import('lightweight-charts').IChartApi & {
            __observer?: ResizeObserver;
          }
        ).__observer = observer;
      },
    );
    return () => {
      disposed = true;
      const observer = (
        chart as
          | (import('lightweight-charts').IChartApi & {
              __observer?: ResizeObserver;
            })
          | undefined
      )?.__observer;
      observer?.disconnect();
      chart?.remove();
    };
  }, [kind, points, timeZone]);
  return (
    <div ref={ref} className="h-[260px] w-full" aria-label={`${kind} chart`} />
  );
}
