import { describe, expect, it } from 'vitest';
import { formatInstrumentDisplay } from '../lib/instrument';

describe('formatInstrumentDisplay', () => {
  it('strips underscore from EUR_USD', () => {
    expect(formatInstrumentDisplay('EUR_USD')).toBe('EURUSD');
  });
  it('strips slash from EUR/USD', () => {
    expect(formatInstrumentDisplay('EUR/USD')).toBe('EURUSD');
  });
  it('strips underscore from XAU_USD', () => {
    expect(formatInstrumentDisplay('XAU_USD')).toBe('XAUUSD');
  });
  it('strips underscore from BTC_USD', () => {
    expect(formatInstrumentDisplay('BTC_USD')).toBe('BTCUSD');
  });
  it('guards empty string', () => {
    expect(formatInstrumentDisplay('')).toBe('');
  });
  it('guards null and undefined', () => {
    expect(formatInstrumentDisplay(null)).toBe('');
    expect(formatInstrumentDisplay(undefined)).toBe('');
  });
  it('preserves casing and alphanumerics without separators', () => {
    expect(formatInstrumentDisplay('EURUSD')).toBe('EURUSD');
    expect(formatInstrumentDisplay('eur_usd')).toBe('eurusd');
  });
  it('strips multiple separators globally', () => {
    expect(formatInstrumentDisplay('EUR_/USD')).toBe('EURUSD');
    expect(formatInstrumentDisplay('A_B/C_D')).toBe('ABCD');
  });
});
