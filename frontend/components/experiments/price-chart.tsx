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
import { ErrorPanel } from './load-status';
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

export function PriceChart({ id }: { id: string }) {
  const { timeZone } = useDisplayTimeZone();
  const [analysis, setAnalysis] = useState<Json | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    atlasApi
      .getPriceAnalysis(id)
      .then((value) => {
        if (active) setAnalysis(object(value));
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason));
      });
    return () => {
      active = false;
    };
  }, [id]);

  const diagnostics = object(analysis?.diagnostics);
  const tradingWindow = object(analysis?.tradingWindow);
  const truncated = diagnostics.truncated === true;
  const omitted = object(diagnostics.omittedRange);
  const omittedDescription = truncated
    ? `${text(diagnostics.omittedM15Count, '0')} M15 candles and ${text(diagnostics.omittedTradeCount, '0')} Trades omitted${omitted.start && omitted.end ? ` · ${formatChartTime(new Date(String(omitted.start)).getTime() / 1000, timeZone)} → ${formatChartTime(new Date(String(omitted.end)).getTime() / 1000, timeZone)}` : ''}.`
    : '';

  return (
    <section aria-labelledby="price-analysis-heading" className="space-y-4">
      <div>
        <h2 id="price-analysis-heading" className="text-lg font-semibold">
          Price analysis
        </h2>
        <p className="text-sm text-atlas-foreground-muted">
          {text(
            object(analysis?.provenance).analyticalSeries,
            'M15 analytical',
          )}{' '}
          — persisted analytical M15 candles and the Experiment’s authoritative
          EMA. Times shown in {timeZone}.
        </p>
      </div>
      {error ? (
        <ErrorPanel message={error} retry={() => window.location.reload()} />
      ) : !analysis ? (
        <div className="rounded-lg border border-atlas-border bg-atlas-surface p-5 text-sm text-atlas-foreground-muted">
          Loading price analysis…
        </div>
      ) : (
        <>
          <div className="rounded-lg border border-atlas-border bg-atlas-surface p-3">
            <PriceAnalysisCanvas analysis={analysis} timeZone={timeZone} />
            {Array.isArray(analysis.trades) && analysis.trades.length === 0 && (
              <p className="border-t border-atlas-border px-2 pt-3 text-sm text-atlas-foreground-muted">
                No trades were generated in this period.
              </p>
            )}
          </div>
          <div
            className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-atlas-foreground-muted"
            aria-label="Price analysis legend"
          >
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-atlas-foreground-muted" />
              EMA
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-atlas-primary" />
              Window
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-atlas-positive" />
              Entry / target
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-atlas-negative" />
              Exit / stop
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-atlas-sweep" />
              Strategy facts
            </span>
            <span>
              <i className="mr-1 inline-block size-2 rounded-full bg-atlas-warning" />
              Trigger
            </span>
          </div>
          {Array.isArray(analysis.landmarks) &&
            analysis.landmarks.length > 0 && (
              <div className="rounded-md border border-atlas-border bg-atlas-surface-hover p-3">
                <h3 className="text-sm font-medium">Trade landmarks</h3>
                <ul className="mt-2 grid gap-2 text-xs text-atlas-foreground-muted sm:grid-cols-2">
                  {analysis.landmarks.map((raw, index) => {
                    const landmark = object(raw);
                    return (
                      <li key={`${text(landmark.kind, 'landmark')}-${index}`}>
                        <span className="font-medium text-atlas-foreground">
                          {text(landmark.kind, 'Landmark')}
                        </span>{' '}
                        · {dateLabel(landmark.time, timeZone)} ·{' '}
                        {priceLabel(landmark.price)}
                        {landmark.trade_sequence
                          ? ` · Trade ${text(landmark.trade_sequence)}`
                          : ''}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          {truncated && (
            <p className="rounded-md border border-atlas-warning bg-atlas-warning-muted p-3 text-sm text-atlas-warning">
              <strong>Chart truncated.</strong> {omittedDescription} This view
              does not cover the full result period.
            </p>
          )}
        </>
      )}
      {analysis ? (
        tradingWindow.start && tradingWindow.end ? (
          <p className="text-xs text-atlas-foreground-muted">
            Trading window:{' '}
            {formatChartTime(
              new Date(String(tradingWindow.start)).getTime() / 1000,
              timeZone,
            )}{' '}
            →{' '}
            {formatChartTime(
              new Date(String(tradingWindow.end)).getTime() / 1000,
              timeZone,
            )}
          </p>
        ) : null
      ) : null}
    </section>
  );
}

export function PriceAnalysisCanvas({
  analysis,
  timeZone,
}: {
  analysis: Json;
  timeZone: Parameters<typeof formatInstant>[1];
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let instance: import('lightweight-charts').IChartApi | undefined;
    let observer: ResizeObserver | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({
        createChart,
        CandlestickSeries,
        LineSeries,
        ColorType,
        createSeriesMarkers,
      }) => {
        if (
          createChart.length > 0 &&
          typeof navigator !== 'undefined' &&
          navigator.userAgent.includes('jsdom')
        )
          return;
        if (!ref.current || disposed) return;
        instance = createChart(ref.current, {
          height: 440,
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
          localization: {
            timeFormatter: (time: number) => formatChartTime(time, timeZone),
          },
          timeScale: {
            tickMarkFormatter: (time: number) =>
              formatChartTick(time, timeZone),
          },
          rightPriceScale: {
            autoScale: true,
            scaleMargins: { top: 0.12, bottom: 0.12 },
          },
        });
        const candles = instance.addSeries(CandlestickSeries, {
          upColor: chartRoles.positive,
          downColor: chartRoles.negative,
          borderVisible: false,
          wickUpColor: chartRoles.positive,
          wickDownColor: chartRoles.negative,
        });
        const ema = instance.addSeries(LineSeries, {
          color: chartRoles.foregroundMuted,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        const toTime = (value: unknown) => {
          const epoch = new Date(String(value)).getTime() / 1000;
          return Number.isFinite(epoch)
            ? (epoch as import('lightweight-charts').Time)
            : null;
        };
        const rows = Array.isArray(analysis.m15) ? analysis.m15 : [];
        const candleData = rows
          .map((raw) => {
            const item = object(raw);
            const time = toTime(item.t);
            return time === null
              ? null
              : {
                  time,
                  open: Number(item.o),
                  high: Number(item.h),
                  low: Number(item.l),
                  close: Number(item.c),
                };
          })
          .filter(
            (
              item,
            ): item is {
              time: import('lightweight-charts').Time;
              open: number;
              high: number;
              low: number;
              close: number;
            } =>
              item !== null &&
              [item.open, item.high, item.low, item.close].every(
                Number.isFinite,
              ),
          );
        const emaData = (Array.isArray(analysis.ema) ? analysis.ema : [])
          .map((raw) => {
            const item = object(raw);
            const time = toTime(item.t);
            const value = Number(item.v);
            return time === null || !Number.isFinite(value)
              ? null
              : { time, value };
          })
          .filter(
            (
              item,
            ): item is {
              time: import('lightweight-charts').Time;
              value: number;
            } => item !== null,
          );
        candles.setData(strictlyAscending(candleData));
        ema.setData(strictlyAscending(emaData));
        const markerItems: Array<{
          time: import('lightweight-charts').Time;
          position: 'aboveBar' | 'belowBar';
          color: string;
          shape: 'circle' | 'arrowUp' | 'arrowDown';
          text: string;
        }> = [];
        const tradingWindow = object(analysis.tradingWindow);
        (
          [
            ['start', tradingWindow.start],
            ['end', tradingWindow.end],
          ] as const
        ).forEach(([label, value]) => {
          const time = toTime(value);
          if (time !== null)
            markerItems.push({
              time,
              position: 'aboveBar',
              color: chartRoles.primary,
              shape: 'circle',
              text: `${label === 'start' ? 'Start' : 'End'} · ${formatChartTime(Number(time), timeZone)}`,
            });
        });
        const tradeRows = Array.isArray(analysis.trades) ? analysis.trades : [];
        tradeRows.forEach((raw) => {
          const trade = object(raw);
          const sequence = text(trade.sequence, '?');
          [
            ['entry', trade.entry, 'arrowUp', 'belowBar', chartRoles.positive],
            ['exit', trade.exit, 'arrowDown', 'aboveBar', chartRoles.negative],
          ].forEach(([label, point, shape, position, color]) => {
            const item = object(point);
            const time = toTime(item.t);
            if (time !== null)
              markerItems.push({
                time,
                position: position as 'aboveBar' | 'belowBar',
                color: color as string,
                shape: shape as 'arrowUp' | 'arrowDown',
                text: `Trade ${sequence} ${label}`,
              });
          });
        });
        const landmarkColors: Record<string, string> = {
          reference: chartRoles.sweep,
          sweep: chartRoles.sweep,
          confirmation: chartRoles.warning,
          entry: chartRoles.positive,
          stop: chartRoles.negative,
          target: chartRoles.positive,
          exit: chartRoles.negative,
          trigger: chartRoles.warning,
        };
        (Array.isArray(analysis.landmarks) ? analysis.landmarks : []).forEach(
          (raw) => {
            const landmark = object(raw);
            const time = toTime(landmark.time ?? landmark.timestamp);
            const price = Number(landmark.price);
            const kind = text(landmark.kind, 'landmark').toLowerCase();
            if (time !== null && Number.isFinite(price)) {
              markerItems.push({
                time,
                position:
                  kind === 'entry' || kind === 'trigger'
                    ? 'belowBar'
                    : 'aboveBar',
                color: landmarkColors[kind] ?? chartRoles.foregroundMuted,
                shape:
                  kind === 'entry'
                    ? 'arrowUp'
                    : kind === 'exit'
                      ? 'arrowDown'
                      : 'circle',
                text: `${text(landmark.kind, 'Landmark')} · ${priceLabel(price)}`,
              });
            }
          },
        );
        createSeriesMarkers(
          candles,
          markerItems.sort((a, b) => Number(a.time) - Number(b.time)),
        );
        const addFact = (raw: unknown, color: string) => {
          const fact = object(raw);
          ['reference', 'sweep', 'confirmation'].forEach((kind) => {
            const stage = object(fact[kind]);
            const time = toTime(stage.t);
            const low = Number(stage.low);
            const high = Number(stage.high);
            if (
              time !== null &&
              Number.isFinite(low) &&
              Number.isFinite(high)
            ) {
              const line = instance?.addSeries(LineSeries, {
                color,
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
              });
              line?.setData(
                strictlyAscending([
                  { time, value: low },
                  {
                    time: (Number(time) +
                      0.001) as import('lightweight-charts').Time,
                    value: high,
                  },
                ]),
              );
            }
          });
        };
        (Array.isArray(analysis.reference) ? analysis.reference : []).forEach(
          (fact) => addFact(fact, chartRoles.sweep),
        );
        tradeRows.forEach((raw) => {
          const trade = object(raw);
          ['stop', 'target'].forEach((kind) => {
            const level = object(trade[kind]);
            const from = toTime(level.from);
            const to = toTime(level.to);
            const price = Number(level.price);
            if (from !== null && to !== null && Number.isFinite(price)) {
              const line = instance?.addSeries(LineSeries, {
                color:
                  kind === 'stop' ? chartRoles.negative : chartRoles.positive,
                lineWidth: 1,
                lineStyle: 2,
                priceLineVisible: false,
                lastValueVisible: false,
              });
              line?.setData(
                strictlyAscending([
                  { time: from, value: price },
                  {
                    time:
                      Number(to) === Number(from)
                        ? ((Number(to) +
                            0.001) as import('lightweight-charts').Time)
                        : to,
                    value: price,
                  },
                ]),
              );
            }
          });
        });
        instance.timeScale().fitContent();
        observer = new ResizeObserver(() =>
          instance?.applyOptions({
            width: Math.max(ref.current?.clientWidth ?? 0, 1),
          }),
        );
        observer.observe(ref.current);
      },
    );
    return () => {
      disposed = true;
      observer?.disconnect();
      instance?.remove();
    };
  }, [analysis, timeZone]);
  return (
    <div
      ref={ref}
      className="h-[440px] w-full"
      aria-label="Experiment price analysis chart"
    />
  );
}

export function TradePriceChart({
  chart,
  levels,
}: {
  chart: Json;
  levels: Json;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { timeZone } = useDisplayTimeZone();
  useEffect(() => {
    let instance: import('lightweight-charts').IChartApi | undefined;
    let observer: ResizeObserver | undefined;
    let disposed = false;
    void import('lightweight-charts').then(
      ({ createChart, CandlestickSeries, LineSeries, ColorType }) => {
        if (
          createChart.length > 0 &&
          typeof navigator !== 'undefined' &&
          navigator.userAgent.includes('jsdom')
        )
          return;
        if (!ref.current || disposed) return;
        instance = createChart(ref.current, {
          height: 420,
          layout: {
            background: {
              type: ColorType.Solid,
              color: chartRoles.surface,
            },
            textColor: 'var(--atlas-color-foreground-muted)',
          },
          grid: {
            vertLines: { color: 'var(--atlas-color-border)' },
            horzLines: { color: 'var(--atlas-color-border)' },
          },
          localization: {
            timeFormatter: (time: number) => formatChartTime(time, timeZone),
          },
          timeScale: {
            tickMarkFormatter: (time: number) =>
              formatChartTime(time, timeZone),
          },
        });
        const candles = instance.addSeries(CandlestickSeries, {
          upColor: 'var(--atlas-color-positive)',
          downColor: 'var(--atlas-color-negative)',
          borderVisible: false,
          wickUpColor: 'var(--atlas-color-positive)',
          wickDownColor: 'var(--atlas-color-negative)',
        });
        const ema = instance.addSeries(LineSeries, {
          color: 'var(--atlas-color-foreground-muted)',
          lineWidth: 1,
          priceLineVisible: false,
        });
        const rows = Array.isArray(chart.candles) ? chart.candles : [];
        const candleData = rows
          .map((raw) => {
            const item = object(raw);
            return {
              time: (new Date(text(item.time, '')).getTime() /
                1000) as import('lightweight-charts').Time,
              open: Number(text(item.open, '0')),
              high: Number(text(item.high, '0')),
              low: Number(text(item.low, '0')),
              close: Number(text(item.close, '0')),
            };
          })
          .filter((item) => Number.isFinite(item.time));
        const emaData = rows
          .map((raw) => {
            const item = object(raw);
            return {
              time: (new Date(text(item.time, '')).getTime() /
                1000) as import('lightweight-charts').Time,
              value: Number(text(item.ema, '0')),
            };
          })
          .filter((item) => Number.isFinite(item.time) && item.value > 0);
        candles.setData(strictlyAscending(candleData));
        ema.setData(strictlyAscending(emaData));
        const levelMap = {
          entry: levels.entry,
          exit: levels.exit,
          stop: levels.stop,
          target: levels.target,
        };
        Object.entries(levelMap).forEach(([title, raw]) => {
          const price = Number(text(raw, ''));
          if (Number.isFinite(price) && price > 0) {
            candles.createPriceLine({
              price,
              color:
                title === 'stop'
                  ? chartRoles.negative
                  : title === 'target'
                    ? chartRoles.positive
                    : chartRoles.primary,
              lineWidth: 1,
              lineStyle: 2,
              axisLabelVisible: true,
              title,
            });
          }
        });
        instance.timeScale().fitContent();
        observer = new ResizeObserver(() =>
          instance?.applyOptions({ width: ref.current?.clientWidth ?? 0 }),
        );
        observer.observe(ref.current);
      },
    );
    return () => {
      disposed = true;
      observer?.disconnect();
      instance?.remove();
    };
  }, [chart, levels.entry, levels.exit, levels.stop, levels.target, timeZone]);
  return (
    <div
      ref={ref}
      className="h-[420px] w-full"
      aria-label="Trade candlestick chart with EMA"
    />
  );
}
