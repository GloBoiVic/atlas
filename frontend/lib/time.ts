export const DISPLAY_TIME_ZONES = [
  'America/Chicago',
  'America/New_York',
  'Europe/London',
  'UTC',
] as const;
export type DisplayTimeZone = (typeof DISPLAY_TIME_ZONES)[number];
export const DEFAULT_DISPLAY_TIME_ZONE: DisplayTimeZone = 'America/Chicago';
export const DISPLAY_TIME_ZONE_STORAGE_KEY = 'atlas.display-time-zone.v1';

export function isDisplayTimeZone(value: unknown): value is DisplayTimeZone {
  return typeof value === 'string' && (DISPLAY_TIME_ZONES as readonly string[]).includes(value);
}

export function formatInstant(value: unknown, zone: DisplayTimeZone = DEFAULT_DISPLAY_TIME_ZONE): string {
  if (typeof value !== 'string' && typeof value !== 'number') return '—';
  const date = new Date(value);
  if (!Number.isFinite(date.valueOf())) return typeof value === 'string' ? value : '—';
  return new Intl.DateTimeFormat('en-US', {
    timeZone: zone, year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true, timeZoneName: 'short',
  }).format(date);
}

export function formatChartTime(value: number, zone: DisplayTimeZone = DEFAULT_DISPLAY_TIME_ZONE): string {
  return formatInstant(value * 1000, zone);
}

export function utcInputFromInstant(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    return parseUtcInput(value) ? value : '';
  }
  const date = new Date(value);
  if (!Number.isFinite(date.valueOf())) return '';
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

export function parseUtcInput(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [, yearText, monthText, dayText, hourText, minuteText] = match;
  const [year, month, day, hour, minute] = [yearText, monthText, dayText, hourText, minuteText].map(Number);
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59 || minute % 15 !== 0) return null;
  const instant = new Date(0);
  instant.setUTCFullYear(year, month - 1, day);
  instant.setUTCHours(hour, minute, 0, 0);
  if (!Number.isFinite(instant.valueOf()) || instant.getUTCFullYear() !== year || instant.getUTCMonth() !== month - 1 || instant.getUTCDate() !== day || instant.getUTCHours() !== hour || instant.getUTCMinutes() !== minute) return null;
  return instant.toISOString();
}

export function formatUtcWallClock(value: unknown): string {
  if (typeof value !== 'string' && typeof value !== 'number') return 'Unknown';
  const date = new Date(value);
  if (!Number.isFinite(date.valueOf())) return 'Unknown';
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date);
}

export function formatChartTick(value: number, zone: DisplayTimeZone = DEFAULT_DISPLAY_TIME_ZONE): string {
  if (!Number.isFinite(value)) return '—';
  const date = new Date(value * 1000);
  if (!Number.isFinite(date.valueOf())) return '—';
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(date).reduce<Record<string, string>>((out, part) => { out[part.type] = part.value; return out; }, {});
  if (parts.hour === '24' ? parts.minute === '00' : parts.hour === '00' && parts.minute === '00') {
    return new Intl.DateTimeFormat('en-US', { timeZone: zone, year: 'numeric', month: 'short', day: 'numeric' }).format(date);
  }
  return formatChartTime(value, zone);
}
