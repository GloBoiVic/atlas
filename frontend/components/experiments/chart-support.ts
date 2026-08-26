import { formatChartTick, formatChartTime } from '../../lib/time';

const chartRoleVariables = {
  background: 'var(--atlas-color-background)',
  surface: 'var(--atlas-color-surface)',
  border: 'var(--atlas-color-border)',
  foregroundMuted: 'var(--atlas-color-foreground-muted)',
  primary: 'var(--atlas-color-primary)',
  positive: 'var(--atlas-color-positive)',
  negative: 'var(--atlas-color-negative)',
  warning: 'var(--atlas-color-warning)',
  sweep: 'var(--atlas-color-sweep)',
} as const;

/**
 * Lightweight Charts paints to canvas and cannot resolve CSS `var(...)`
 * values itself. Resolve Atlas tokens at the browser boundary so charts keep
 * the design system as their source of truth without falling back to black.
 */
const resolveChartColor = (value: string) => {
  if (typeof document === 'undefined') return value;
  const variable = value.match(/^var\((--[^)]+)\)$/)?.[1];
  if (!variable) return value;
  return (
    getComputedStyle(document.documentElement)
      .getPropertyValue(variable)
      .trim() || value
  );
};

export const chartRoles = new Proxy(chartRoleVariables, {
  get(target, property: keyof typeof chartRoleVariables) {
    return resolveChartColor(target[property]);
  },
});

type DisplayZone = Parameters<typeof formatChartTime>[1];
export const chartTime = (time: number, zone?: DisplayZone) =>
  formatChartTime(time, zone);
export const chartTick = (time: number, zone?: DisplayZone) =>
  formatChartTick(time, zone);

export type Json = Record<string, unknown>;
export type ChartPoint = { time: import('lightweight-charts').Time };

/** Lightweight Charts rejects non-ascending or duplicate timestamps. */
export const strictlyAscending = <T extends ChartPoint>(points: T[]): T[] => {
  const sorted = [...points].sort((a, b) => Number(a.time) - Number(b.time));
  return sorted.filter(
    (point, index) =>
      index === 0 || Number(point.time) > Number(sorted[index - 1].time),
  );
};
