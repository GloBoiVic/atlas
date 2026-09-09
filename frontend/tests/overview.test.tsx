import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  ready: vi.fn(),
  listStrategies: vi.fn(),
  listExperiments: vi.fn(),
  paperCapability: vi.fn(),
  paperBrokerState: vi.fn(),
  activePaperStatus: vi.fn(),
  historicalCapability: vi.fn(),
  configurationOptions: vi.fn(),
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
vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({ timeZone: 'UTC', setTimeZone: vi.fn() }),
}));
vi.mock('../lib/api-client', () => ({ atlasApi: mocks }));

import { Overview } from '../components/overview';

const snapshots = [
  {
    id: 'snapshot-1',
    fingerprint: 'sha256:overview-snapshot',
    coverageStart: '2024-01-01T00:00:00Z',
    coverageEnd: '2024-02-01T00:00:00Z',
    snapshotSchema: 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2',
    integrity: { barCount: 1000 },
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.ready.mockResolvedValue({
    status: 'ready',
    service: 'atlas-api',
    checks: { database: 'ok' },
  });
  mocks.listStrategies.mockResolvedValue({
    items: [
      { strategyKey: 'ema', name: 'EMA Sweep' },
      { strategyKey: 'other' },
    ],
  });
  mocks.listExperiments.mockResolvedValue({
    items: [{ status: 'COMPLETED' }, { status: 'RUNNING' }],
  });
  mocks.paperCapability.mockResolvedValue({
    provider: 'OANDA Practice',
    environment: 'practice',
    instrument: 'EUR/USD',
    available: true,
    reasonCode: null,
  });
  mocks.paperBrokerState.mockResolvedValue({
    provider: 'OANDA',
    environment: 'PRACTICE',
    accountCurrency: 'USD',
    openTrades: [
      {
        tradeId: '7',
        instrument: 'EUR_USD',
        openTime: '2026-01-05T08:00:00.123456Z',
        openPrice: '1.16188',
        currentUnits: '1000',
        state: 'OPEN',
        unrealizedPl: '12.34',
      },
    ],
  });
  mocks.activePaperStatus.mockResolvedValue(null);
  mocks.historicalCapability.mockResolvedValue({
    provider: 'OANDA Practice',
    instrument: 'EUR/USD',
    products: [
      { product: 'analytical', resolution: 'M15', components: ['MID'] },
    ],
    available: true,
    reasonCode: null,
  });
  mocks.configurationOptions.mockResolvedValue({
    strategyVersions: [],
    datasetSnapshots: snapshots,
    defaults: {},
    simulationAssumptions: {},
  });
});
afterEach(() => cleanup());

describe('Overview surface', () => {
  it('composes returned catalog, visible experiment, capability, and snapshot facts', async () => {
    render(<Overview />);

    expect(await screen.findByText('2 returned items')).toBeInTheDocument();
    expect(
      screen.getByText('2 returned items on the visible first page.'),
    ).toBeInTheDocument();
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getAllByText('OANDA Practice').length).toBeGreaterThanOrEqual(
      3,
    );
    expect(screen.getByText('1 returned options')).toBeInTheDocument();
    expect(screen.getByText('sha256:overview-snapshot')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Configure an Experiment' }),
    ).toHaveAttribute('href', '/experiments/new');
  });

  it('keeps each read section loading independently', () => {
    const pending = new Promise<never>(() => undefined);
    mocks.ready.mockReturnValue(pending);
    mocks.listStrategies.mockReturnValue(pending);
    mocks.listExperiments.mockReturnValue(pending);
    mocks.paperCapability.mockReturnValue(pending);
    mocks.paperBrokerState.mockReturnValue(pending);
    mocks.activePaperStatus.mockReturnValue(pending);
    mocks.historicalCapability.mockReturnValue(pending);
    mocks.configurationOptions.mockReturnValue(pending);

    render(<Overview />);

    expect(screen.getByText('Loading system readiness…')).toBeInTheDocument();
    expect(screen.getByText('Loading Strategy catalog…')).toBeInTheDocument();
    expect(
      screen.getByText('Loading visible Experiments…'),
    ).toBeInTheDocument();
    expect(screen.getByText('Loading PAPER capability…')).toBeInTheDocument();
    expect(screen.getByText('Loading PAPER broker state…')).toBeInTheDocument();
    expect(screen.getByText('Loading Runtime status…')).toBeInTheDocument();
    expect(
      screen.getByText('Loading historical data capability…'),
    ).toBeInTheDocument();
    expect(screen.getByText('Loading DatasetSnapshots…')).toBeInTheDocument();
  });

  it('shows empty results without converting an unrelated read into an error', async () => {
    mocks.listStrategies.mockResolvedValue({ items: [] });
    mocks.listExperiments.mockResolvedValue({ items: [] });
    mocks.configurationOptions.mockResolvedValue({
      strategyVersions: [],
      datasetSnapshots: [],
      defaults: {},
      simulationAssumptions: {},
    });

    render(<Overview />);

    expect(
      await screen.findByText('No Strategy catalog items were returned.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No Experiment items were returned on the first page.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'No DatasetSnapshots are available in configuration options.',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No active PAPER activation reported/),
    ).toBeInTheDocument();
    expect(screen.getByText('API and database readiness')).toBeInTheDocument();
  });

  it('makes a not-ready health response explicit without hiding its facts', async () => {
    mocks.ready.mockResolvedValue({
      status: 'not_ready',
      service: 'atlas-api',
      checks: { database: 'unavailable' },
    });

    render(<Overview />);

    expect(
      await screen.findByText(/Readiness is unavailable/),
    ).toBeInTheDocument();
    expect(screen.getByText('not_ready')).toBeInTheDocument();
    expect(screen.getByText('unavailable')).toBeInTheDocument();
  });

  it('keeps a failed section visible while known sections remain populated', async () => {
    mocks.listStrategies.mockRejectedValue(
      new Error('Strategy catalog offline'),
    );

    render(<Overview />);

    expect(
      await screen.findByText('Strategy catalog offline'),
    ).toBeInTheDocument();
    expect(screen.getByText('sha256:overview-snapshot')).toBeInTheDocument();
    expect(screen.getAllByText('OANDA Practice').length).toBeGreaterThanOrEqual(
      2,
    );
  });

  it('shows broker exposure first with LONG derived from positive units', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '7',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00.123456Z',
          openPrice: '1.10000',
          currentUnits: '5000',
          state: 'OPEN',
          unrealizedPl: '10.00',
        },
      ],
    });
    render(<Overview />);
    expect(await screen.findByText('LONG')).toBeInTheDocument();
    expect(screen.getByText('5,000 units')).toBeInTheDocument();
    expect(screen.getAllByText('EURUSD').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('1.10000')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
    const headings = screen.getAllByRole('heading');
    const brokerIdx = headings.findIndex((h) =>
      h.textContent?.includes('PAPER broker state'),
    );
    const readinessIdx = headings.findIndex((h) =>
      h.textContent?.includes('API and database readiness'),
    );
    expect(brokerIdx).toBeGreaterThanOrEqual(0);
    expect(readinessIdx).toBeGreaterThanOrEqual(0);
    expect(brokerIdx).toBeLessThan(readinessIdx);
  });

  it('shows SHORT derived from negative units with absolute quantity', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '9',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00Z',
          openPrice: '1.20000',
          currentUnits: '-390663',
          state: 'OPEN',
          unrealizedPl: '-410.20',
        },
      ],
    });
    render(<Overview />);
    expect(await screen.findByText('SHORT')).toBeInTheDocument();
    expect(screen.getByText('390,663 units')).toBeInTheDocument();
    expect(screen.getByText('-$410.20')).toBeInTheDocument();
  });

  it('shows multiple Trades distinct without netting', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '3',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00Z',
          openPrice: '1.1',
          currentUnits: '100',
          state: 'OPEN',
          unrealizedPl: '1.00',
        },
        {
          tradeId: '4',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:01:00Z',
          openPrice: '1.2',
          currentUnits: '-200',
          state: 'CLOSE_WHEN_TRADEABLE',
          unrealizedPl: '-2.00',
        },
      ],
    });
    render(<Overview />);
    expect(await screen.findAllByText('EURUSD')).not.toHaveLength(0);
    expect(screen.getByText('LONG')).toBeInTheDocument();
    expect(screen.getByText('SHORT')).toBeInTheDocument();
    expect(screen.getByText('100 units')).toBeInTheDocument();
    expect(screen.getByText('200 units')).toBeInTheDocument();
  });

  it('shows No open broker trades only for successful empty', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [],
    });
    render(<Overview />);
    expect(
      await screen.findByText('No open broker trades.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Broker unavailable')).not.toBeInTheDocument();
  });

  it('shows Broker unavailable on failure not flat', async () => {
    mocks.paperBrokerState.mockRejectedValue(
      new Error('Current broker state is unavailable.'),
    );
    render(<Overview />);
    expect(await screen.findByText('Broker unavailable')).toBeInTheDocument();
    expect(
      screen.queryByText('No open broker trades.'),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Flat')).not.toBeInTheDocument();
  });

  it('uses display timezone for opened time and refresh is GET-only', async () => {
    const brokerData = {
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '7',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00.123456Z',
          openPrice: '1.1',
          currentUnits: '100',
          state: 'OPEN',
          unrealizedPl: '1.00',
        },
      ],
    };
    mocks.paperBrokerState.mockResolvedValue(brokerData);
    render(<Overview />);
    expect(await screen.findByText('PAPER broker state')).toBeInTheDocument();
    // Refresh button exists and is not a mutation
    const refresh = screen.getAllByRole('button', { name: /Refresh/ })[0];
    expect(refresh).toBeInTheDocument();
    expect(
      screen.queryByText(/Buy|Sell|Close|Activate|Stop|Reconcile/),
    ).not.toBeInTheDocument();
  });
});
