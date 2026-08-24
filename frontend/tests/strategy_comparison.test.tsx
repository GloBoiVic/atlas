import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  listStrategies: vi.fn(),
  getStrategy: vi.fn(),
  compareExperiments: vi.fn(),
}));
vi.mock('../components/app-shell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));
vi.mock('next/navigation', () => ({
  useParams: () => ({ strategyKey: 'ema_sweep_engulfing' }),
  useSearchParams: () =>
    new URLSearchParams('experimentId=one&experimentId=two'),
}));
vi.mock('../lib/api-client', () => ({ atlasApi: mocks }));
import { StrategyDetailPage } from '../components/strategy-history';
import { ExperimentComparisonPage } from '../components/experiment-comparison';

beforeEach(() => vi.clearAllMocks());

describe('Phase 6 strategy and comparison views', () => {
  it('shows Atlas version identity, fixed window, provenance, and usage', async () => {
    mocks.getStrategy.mockResolvedValue({
      name: 'EMA Sweep Engulfing',
      description: 'Methodology',
      versions: [
        {
          id: 'v2',
          displayName: 'EMA Sweep Engulfing v2',
          versionNumber: 2,
          implementationKey: 'ema_sweep_engulfing.v2',
          sourceFingerprint: 'fingerprint',
          createdAt: '2026-08-23T12:00:00Z',
          gitSha: null,
          parameterSchema: [
            {
              key: 'ema_period',
              label: 'EMA period',
              type: 'integer',
              min: 20,
              max: 200,
            },
            {
              key: 'expiry_window',
              label: 'Expiry window',
              type: 'integer',
              min: 5,
              max: 5,
            },
          ],
          timeframe: '15m',
          warmUpBars: 200,
          capabilities: [],
          experimentCount: 3,
          lastUsedAt: null,
          executionAvailable: true,
          unavailableReason: null,
        },
      ],
    });
    render(<StrategyDetailPage />);
    expect(
      await screen.findByText('EMA Sweep Engulfing v2'),
    ).toBeInTheDocument();
    expect(screen.getByText('Expiry window')).toBeInTheDocument();
    expect(screen.getByText(/Expiry window · 5 bars/)).toBeInTheDocument();
    expect(screen.getByText('fingerprint')).toBeInTheDocument();
  });

  it('keeps comparison order and puts warnings before canonical metrics', async () => {
    mocks.compareExperiments.mockResolvedValue({
      experiments: [
        {
          id: 'one',
          slot: 'A',
          label: 'Experiment A · first',
          strategy: { name: 'EMA Sweep Engulfing', version: 2 },
          metrics: {
            netReturn: { state: 'VALUE', value: '0.1' },
            tradeCount: { state: 'VALUE', value: '2' },
          },
        },
        {
          id: 'two',
          slot: 'B',
          label: 'Experiment B · second',
          strategy: { name: 'EMA Sweep Engulfing', version: 2 },
          metrics: {
            netReturn: { state: 'UNAVAILABLE', reason: 'ZERO_TRADES' },
            tradeCount: { state: 'VALUE', value: '0' },
          },
        },
      ],
      differences: [
        { path: 'parameters.ema_period', values: { A: 100, B: 120 } },
      ],
      warnings: [
        {
          code: 'DATASET_SNAPSHOT_DIFFERS',
          severity: 'CAUTION',
          explanation: 'Historical DatasetSnapshot provenance differs.',
          paths: ['datasetSnapshot'],
        },
      ],
      changedParameterKeys: ['ema_period'],
      strongParameterIsolation: false,
    });
    render(<ExperimentComparisonPage />);
    expect(
      await screen.findByRole('heading', { name: 'Canonical metrics' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Comparability warnings')).toBeInTheDocument();
    expect(screen.getByText('Configuration facts')).toBeInTheDocument();
    expect(
      screen.getByText('Historical DatasetSnapshot provenance differs.'),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.compareExperiments).toHaveBeenCalledWith(['one', 'two']),
    );
    expect(screen.getByText('UNAVAILABLE · ZERO_TRADES')).toBeInTheDocument();
  });
});
