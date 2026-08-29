import { describe, expect, it } from 'vitest';
import {
  experimentHeadlineMetrics,
  experimentIdentity,
  experimentPeriod,
  statusLabel,
} from '../components/experiments/shared';

describe('historical Experiment list presentation helpers', () => {
  it('keeps human identity and period separate from raw identifiers', () => {
    const item = {
      id: 'raw-id',
      label: 'EUR/USD · 2024 study',
      status: 'COMPLETED',
      tradingStart: '2024-01-01T00:00:00Z',
      tradingEnd: '2024-01-02T00:00:00Z',
    };

    expect(experimentIdentity(item)).toBe('EUR/USD · 2024 study');
    expect(experimentPeriod(item, 'UTC')).toContain('Jan 1, 2024');
    expect(statusLabel(item.status)).toBe('COMPLETED');
  });

  it('preserves canonical metric display states', () => {
    expect(
      experimentHeadlineMetrics({
        metrics: {
          netReturn: { state: 'VALUE', value: '0.125' },
          maxDrawdownPercent: { state: 'UNAVAILABLE', reason: 'ZERO_TRADES' },
          profitFactor: { state: 'INFINITE' },
          tradeCount: { state: 'VALUE', value: '0' },
        },
      }),
    ).toEqual({
      netReturn: '12.50%',
      maxDrawdown: '—',
      sharpe: '—',
      trades: '0',
    });
  });
});
