import { describe, expect, it } from 'vitest';
import {
  formatPaperLifecycle,
  formatPaperOperationalPhase,
  percentageToDecimalRatio,
} from '../lib/paper-control';

describe('PAPER control helpers', () => {
  it.each([
    ['1', '0.01'],
    ['0.5', '0.005'],
    ['12.5', '0.125'],
    ['99.99', '0.9999'],
  ])('converts %s percent to exact ratio %s', (percentage, ratio) => {
    expect(percentageToDecimalRatio(percentage)).toBe(ratio);
  });

  it.each(['', '0', '0.0', '100', '100.0', '-1', '101', 'NaN', '1e0'])(
    'rejects invalid risk percentage %s',
    (percentage) => {
      expect(() => percentageToDecimalRatio(percentage)).toThrow();
    },
  );

  it('preserves precision for fractional percentages without binary arithmetic', () => {
    expect(percentageToDecimalRatio('0.00000000001')).toBe('0.0000000000001');
    expect(percentageToDecimalRatio('99.99999999999')).toBe('0.9999999999999');
  });

  it('maps lifecycle states without collapsing REQUESTED into Running', () => {
    expect(formatPaperLifecycle('REQUESTED')).toBe(
      'Approved — waiting for Atlas runtime',
    );
    expect(formatPaperLifecycle('STARTING')).toBe('Starting');
    expect(formatPaperLifecycle('RUNNING')).toBe('Running');
    expect(formatPaperLifecycle('STOP_REQUESTED')).toBe('Stopping');
    expect(formatPaperLifecycle('BLOCKED')).toBe('Blocked');
    expect(formatPaperLifecycle('UNKNOWN')).toBe('UNKNOWN');
  });

  it('maps operational phases to readable secondary labels', () => {
    expect(formatPaperOperationalPhase('IDLE')).toBe('Waiting');
    expect(formatPaperOperationalPhase('WAITING_FRONTIER')).toBe(
      'Waiting for next market frontier',
    );
    expect(formatPaperOperationalPhase('EVALUATING')).toBe(
      'Evaluating Strategy',
    );
    expect(formatPaperOperationalPhase('EXECUTING')).toBe(
      'Executing approved Trade',
    );
    expect(formatPaperOperationalPhase('UNKNOWN')).toBe('UNKNOWN');
  });
});
