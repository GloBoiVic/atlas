import { describe, expect, it } from 'vitest';
import { formatInstant, parseUtcInput, utcInputFromInstant } from '../lib/time';

describe('UTC input and display time contract', () => {
  it('serializes only valid, aligned UTC wall-clock values', () => {
    expect(parseUtcInput('2026-03-08T02:15')).toBe('2026-03-08T02:15:00.000Z');
    expect(parseUtcInput('2026-11-01T01:45')).toBe('2026-11-01T01:45:00.000Z');
    expect(parseUtcInput('2026-03-08T02:17')).toBeNull();
    expect(parseUtcInput('2026-02-30T10:00')).toBeNull();
    expect(parseUtcInput('2026-03-08T02:15:00')).toBeNull();
  });
  it('round-trips instants through UTC fields independent of Chicago DST', () => {
    expect(utcInputFromInstant('2026-03-08T02:15:00Z')).toBe('2026-03-08T02:15');
    expect(utcInputFromInstant('2026-11-01T01:45:00Z')).toBe('2026-11-01T01:45');
    expect(utcInputFromInstant('2026-03-08T02:15')).toBe('2026-03-08T02:15');
  });
  it('distinguishes fall-back abbreviations in the selected display zone', () => {
    expect(formatInstant('2026-11-01T06:30:00Z', 'America/Chicago')).toContain('CDT');
    expect(formatInstant('2026-11-01T07:30:00Z', 'America/Chicago')).toContain('CST');
  });
});
