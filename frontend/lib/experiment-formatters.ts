import { formatChartTick, formatChartTime, formatInstant } from './time';

export type MetricDisplayState = 'VALUE' | 'INFINITE' | 'UNAVAILABLE';
export type MetricValue = {
  state?: MetricDisplayState;
  value?: unknown;
  reason?: unknown;
};

const numberValue = (value: unknown) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

export const unavailableLabel = (reason?: unknown) => ({
  value: '—',
  reason:
    typeof reason === 'string' && reason
      ? reason
      : 'Not available for this result',
});

export const formatPercent = (value: unknown) => {
  const number = numberValue(value);
  return number === null ? '—' : `${(number * 100).toFixed(2)}%`;
};
export const formatMoney = (value: unknown) => {
  const number = numberValue(value);
  return number === null
    ? '—'
    : `${number >= 0 ? '+' : '-'}$${Math.abs(number).toFixed(2)}`;
};
export const formatCurrency = (value: unknown) => {
  const number = numberValue(value);
  return number === null
    ? '—'
    : new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(number);
};
export const formatRatio = (value: unknown) => {
  const number = numberValue(value);
  return number === null ? '—' : `${number.toFixed(2)}x`;
};
export const formatInteger = (value: unknown) => {
  const number = numberValue(value);
  return number === null ? '—' : Math.trunc(number).toLocaleString('en-US');
};
export const formatPrice = (value: unknown) => {
  const number = numberValue(value);
  return number === null ? '—' : number.toFixed(5);
};
export const formatMetric = (
  metric: MetricValue,
  format: 'percent' | 'money' | 'ratio' | 'integer' | 'number' = 'number',
) => {
  if (metric.state === 'INFINITE') return '∞';
  if (metric.state !== 'VALUE') return '—';
  if (format === 'percent') return formatPercent(metric.value);
  if (format === 'money') return formatMoney(metric.value);
  if (format === 'ratio') return formatRatio(metric.value);
  if (format === 'integer') return formatInteger(metric.value);
  return String(metric.value ?? '—');
};
export { formatInstant, formatChartTime, formatChartTick };
