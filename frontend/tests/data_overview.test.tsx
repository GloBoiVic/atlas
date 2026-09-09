import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  historicalCapability: vi.fn(),
  configurationOptions: vi.fn(),
  activeHistoricalLoad: vi.fn(),
}));

vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({
    timeZone: 'America/New_York',
    setTimeZone: vi.fn(),
  }),
}));
vi.mock('../lib/api-client', () => ({ atlasApi: mocks }));

import { DataOverview } from '../components/data-overview';

const longFingerprint = `sha256:${'a'.repeat(64)}`;
const longIntegrityValue = `sha256:${'b'.repeat(64)}`;

const snapshot = {
  id: 'snapshot-1',
  fingerprint: longFingerprint,
  coverageStart: '2024-01-01T00:00:00Z',
  coverageEnd: '2024-02-01T00:00:00Z',
  snapshotSchema: 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2',
  integrity: { barCount: 1000, gapCount: 0, contentHash: longIntegrityValue },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.historicalCapability.mockResolvedValue({
    provider: 'OANDA Practice',
    instrument: 'EUR/USD',
    products: [
      { product: 'analytical', resolution: 'M15', components: ['MID'] },
      { product: 'execution', resolution: 'M1', components: ['BID', 'ASK'] },
    ],
    available: true,
    reasonCode: null,
  });
  mocks.configurationOptions.mockResolvedValue({
    strategyVersions: [],
    datasetSnapshots: [snapshot],
    defaults: {},
    simulationAssumptions: {},
  });
  mocks.activeHistoricalLoad.mockResolvedValue(null);
});
afterEach(() => cleanup());

describe('Data read-only surface', () => {
  it('renders snapshot integrity and formats coverage in the display timezone', async () => {
    render(<DataOverview />);

    expect(await screen.findByText(longFingerprint)).toHaveClass('break-all');
    expect(screen.getByText(longIntegrityValue)).toHaveClass('break-all');
    expect(
      screen.getByText('ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Bar Count/)).toBeInTheDocument();
    expect(screen.getByText('1000')).toBeInTheDocument();
    expect(screen.getByText(/Gap Count/)).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.getAllByText(/Dec 31, 2023/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/EST/).length).toBeGreaterThan(0);
    expect(
      screen.getByText('No historical load is active.'),
    ).toBeInTheDocument();
  });

  it('shows unavailable capability and empty snapshot/load states without mutation controls', async () => {
    mocks.historicalCapability.mockResolvedValue({
      provider: 'OANDA Practice',
      instrument: 'EUR/USD',
      products: [],
      available: false,
      reasonCode: 'OANDA_HISTORICAL_UNAVAILABLE',
    });
    mocks.configurationOptions.mockResolvedValue({
      strategyVersions: [],
      datasetSnapshots: [],
      defaults: {},
      simulationAssumptions: {},
    });

    render(<DataOverview />);

    expect(
      await screen.findByText('OANDA_HISTORICAL_UNAVAILABLE'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No historical products were returned.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'No DatasetSnapshots are available in configuration options.',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No historical load is active.'),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryByText(/Load|Resume/)).not.toBeInTheDocument();
  });

  it('keeps configuration errors independent from known capability facts', async () => {
    mocks.configurationOptions.mockRejectedValue(
      new Error('configuration read failed'),
    );
    render(<DataOverview />);

    expect(
      await screen.findByText('configuration read failed'),
    ).toBeInTheDocument();
    const retry = screen.getByRole('button', { name: 'Retry' });
    expect(retry).toHaveClass(
      'focus-visible:ring-2',
      'focus-visible:ring-atlas-focus-ring',
    );
    retry.focus();
    expect(retry).toHaveFocus();
    expect(screen.getByText('OANDA Practice')).toBeInTheDocument();
    expect(
      screen.getByText('No historical load is active.'),
    ).toBeInTheDocument();
  });

  it('keeps each data read loading independently', () => {
    const pending = new Promise<never>(() => undefined);
    mocks.historicalCapability.mockReturnValue(pending);
    mocks.configurationOptions.mockReturnValue(pending);
    mocks.activeHistoricalLoad.mockReturnValue(pending);
    render(<DataOverview />);

    expect(
      screen.getByText('Loading historical data capability…'),
    ).toBeInTheDocument();
    expect(screen.getByText('Loading DatasetSnapshots…')).toBeInTheDocument();
    expect(
      screen.getByText('Loading current historical load…'),
    ).toBeInTheDocument();
  });
});
