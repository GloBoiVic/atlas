"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  LineSeries,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";

import type { EquityPoint } from "@/lib/api";

const MAX_POINTS = 2_000;

function cssToken(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function toChartPoints(points: EquityPoint[]): Array<{ time: UTCTimestamp; value: number }> {
  return points
    .slice(-MAX_POINTS)
    .map((point) => ({
      time: Math.floor(new Date(point.timestamp).getTime() / 1_000) as UTCTimestamp,
      value: Number(point.equity),
    }))
    .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value));
}

export function EquityCurveChart({ points }: { points: EquityPoint[] }): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const chart = createChart(container, {
      autoSize: true,
      height: 280,
      layout: {
        background: { color: cssToken("--color-atlas-surface", "#16171f") },
        textColor: cssToken("--color-atlas-fg-secondary", "#9496a1"),
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: cssToken("--color-atlas-border", "#23242f") },
        horzLines: { color: cssToken("--color-atlas-border", "#23242f") },
      },
      rightPriceScale: { borderColor: cssToken("--color-atlas-border", "#23242f") },
      timeScale: {
        borderColor: cssToken("--color-atlas-border", "#23242f"),
        timeVisible: true,
        secondsVisible: false,
      },
      localization: { priceFormatter: (value: number) => value.toString() },
    });
    chartRef.current = chart;

    const series = chart.addSeries(LineSeries, {
      color: cssToken("--color-atlas-accent", "#4e8eff"),
      lineWidth: 2,
      crosshairMarkerVisible: true,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    // setData is intentionally a single bounded batch: equity values are API facts,
    // and the browser only adapts their serialized representation to chart coordinates.
    series.setData(toChartPoints(points));
    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => chart.resize(container.clientWidth, 280));
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [points]);

  return (
    <div
      ref={containerRef}
      className="min-h-70 w-full"
      role="img"
      aria-label="API-provided closed-trade equity curve, with timestamps shown in UTC"
    />
  );
}
