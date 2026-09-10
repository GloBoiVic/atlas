import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  ready: vi.fn(),
  listStrategies: vi.fn(),
  listExperiments: vi.fn(),
  paperBrokerState: vi.fn(),
  listPaperTrades: vi.fn(),
  activePaperStatus: vi.fn(),
  paperStatus: vi.fn(),
  stopPaper: vi.fn(),
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
import { PaperTradeHistory } from '../components/paper-trade-history';

const brokerState = {
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
};

const completedExperiment = {
  id: 'experiment-1',
  label: 'Candle Confirmation Break',
  status: 'COMPLETED',
  identity: {
    strategyVersion: { displayName: 'EMA Sweep v2' },
    tradingPeriod: {
      start: '2026-01-01T00:00:00Z',
      end: '2026-01-02T00:00:00Z',
    },
  },
  metrics: {
    netReturn: { state: 'VALUE', value: 0.017 },
    tradeCount: { state: 'VALUE', value: 1 },
  },
};

const completedPaperTrade = {
  strategyKey: 'ema',
  strategyName: 'EMA Sweep',
  strategyVersionNumber: 2,
  instrument: 'EUR_USD',
  direction: 'SHORT',
  units: '390663.0000000000',
  entryPrice: '1.10000',
  enteredAt: '2026-01-05T08:00:00Z',
  stopPrice: '1.09500',
  targetPrice: '1.11000',
  initialRisk: '0.00500',
  closedAt: '2026-01-05T09:00:00Z',
  averageClosePrice: '1.11000',
  realizedPl: '12.34',
  financing: '-0.10',
  dividendAdjustment: '0',
  exitCause: 'TAKE_PROFIT',
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.ready.mockResolvedValue({
    status: 'ready',
    service: 'atlas-api',
    checks: { database: 'ok' },
  });
  mocks.listStrategies.mockResolvedValue({
    items: [
      {
        strategyKey: 'ema',
        name: 'EMA Sweep',
        description: 'EMA strategy',
        latestVersion: {
          displayName: 'EMA Sweep v2',
          id: 'version-1',
          versionNumber: 2,
        },
        versionCount: 2,
        experimentCount: 4,
        lastExperimentAt: '2026-01-03T00:00:00Z',
      },
      {
        strategyKey: 'other',
        name: 'Other Strategy',
        description: 'Another strategy',
        latestVersion: null,
        versionCount: 0,
        experimentCount: 0,
        lastExperimentAt: null,
      },
    ],
  });
  mocks.listExperiments.mockResolvedValue({
    items: [completedExperiment, { id: 'experiment-2', status: 'RUNNING' }],
  });
  mocks.paperBrokerState.mockResolvedValue(brokerState);
  mocks.listPaperTrades.mockResolvedValue({ items: [completedPaperTrade] });
  mocks.activePaperStatus.mockResolvedValue(null);
  mocks.paperStatus.mockResolvedValue({
    activation: {
      activationId: 'activation-1',
      lifecycleState: 'REQUESTED',
      operationalPhase: 'STARTING',
    },
  });
});
afterEach(() => cleanup());

describe('Overview surface', () => {
  it('presents exposure first and composes trader-facing summaries', async () => {
    render(<Overview />);

    expect(
      screen.getByRole('heading', { name: 'Overview' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'Paper Trading' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'Recent PAPER trades' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Strategies' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Experiments' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'System' })).toBeInTheDocument();
    expect(screen.getByText('EMA Sweep')).toBeInTheDocument();
    expect(screen.getAllByText('EMA Sweep v2')).not.toHaveLength(0);
    expect(screen.getByText('Candle Confirmation Break')).toBeInTheDocument();
    expect(screen.getByText('1.70% · 1 trade')).toBeInTheDocument();
    expect(screen.getByText('EUR/USD')).toBeInTheDocument();
    expect(screen.getByText('SHORT')).toBeInTheDocument();
    expect(screen.getByText('390,663 units')).toBeInTheDocument();
    expect(
      screen.queryByText('390,663.0000000000 units'),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText('Entry')).toHaveLength(2);
    expect(screen.getByText('Exit')).toBeInTheDocument();
    expect(screen.getByText('Stop')).toBeInTheDocument();
    expect(screen.getByText('Target')).toBeInTheDocument();
    expect(screen.getByText('1.10000')).toBeInTheDocument();
    expect(screen.getAllByText('1.11000')).toHaveLength(2);
    expect(screen.getByText('1.09500')).toBeInTheDocument();
    expect(screen.getByText('Jan 5 · 9:00 AM')).toBeInTheDocument();
    expect(screen.getByText('Target hit')).toBeInTheDocument();
    expect(screen.getByText('+$12.34')).toBeInTheDocument();
    expect(screen.getAllByText('Ready')).not.toHaveLength(0);
    expect(screen.getByText('API')).toBeInTheDocument();
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'View Strategies' }),
    ).toHaveAttribute('href', '/strategies');
    expect(
      screen.getByRole('link', { name: 'View Experiments' }),
    ).toHaveAttribute('href', '/experiments');
    expect(
      screen.getByRole('link', { name: 'Run Experiment' }),
    ).toHaveAttribute('href', '/experiments/new');

    const headings = screen.getAllByRole('heading');
    const brokerIndex = headings.findIndex(
      (heading) => heading.textContent === 'Paper Trading',
    );
    const strategyIndex = headings.findIndex(
      (heading) => heading.textContent === 'Strategies',
    );
    expect(brokerIndex).toBeLessThan(strategyIndex);
    expect(screen.queryByText('Strategy catalog')).not.toBeInTheDocument();
    expect(screen.queryByText(/returned items/)).not.toBeInTheDocument();
    expect(screen.queryByText('Next steps')).not.toBeInTheDocument();
    expect(
      screen.queryByText('sha256:overview-snapshot'),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('PAPER capability')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Historical data capability'),
    ).not.toBeInTheDocument();
    expect(mocks.paperBrokerState).toHaveBeenCalledTimes(1);
    expect(mocks.listPaperTrades).toHaveBeenCalledWith({ limit: 3 });
    expect(mocks.activePaperStatus).toHaveBeenCalledTimes(1);
  });

  it('keeps an unavailable exit cause as compact secondary metadata', async () => {
    mocks.listPaperTrades.mockResolvedValue({
      items: [{ ...completedPaperTrade, exitCause: null }],
    });

    render(<PaperTradeHistory compact limit={3} />);

    expect(
      await screen.findByText('Exit cause unavailable'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('Exit cause', { exact: true }),
    ).not.toBeInTheDocument();
  });

  it('keeps every read section loading independently', () => {
    const pending = new Promise<never>(() => undefined);
    mocks.ready.mockReturnValue(pending);
    mocks.listStrategies.mockReturnValue(pending);
    mocks.listExperiments.mockReturnValue(pending);
    mocks.paperBrokerState.mockReturnValue(pending);
    mocks.listPaperTrades.mockReturnValue(pending);
    mocks.activePaperStatus.mockReturnValue(pending);

    render(<Overview />);

    expect(screen.getByText('Loading system readiness…')).toBeInTheDocument();
    expect(screen.getByText('Loading Strategies…')).toBeInTheDocument();
    expect(screen.getByText('Loading Experiments…')).toBeInTheDocument();
    expect(screen.getByText('Loading broker exposure…')).toBeInTheDocument();
    expect(screen.getByText('Loading runtime…')).toBeInTheDocument();
    expect(
      screen.getByText('Loading recent PAPER trades…'),
    ).toBeInTheDocument();
  });

  it('keeps successful empty states concise and independent', async () => {
    mocks.listStrategies.mockResolvedValue({ items: [] });
    mocks.listExperiments.mockResolvedValue({ items: [] });
    mocks.paperBrokerState.mockResolvedValue({
      ...brokerState,
      openTrades: [],
    });
    mocks.listPaperTrades.mockResolvedValue({ items: [] });

    render(<Overview />);

    expect(await screen.findByText('No Strategies')).toBeInTheDocument();
    expect(screen.getByText('No Experiments')).toBeInTheDocument();
    expect(screen.getByText('No open trades')).toBeInTheDocument();
    expect(screen.getByText('No active runtime')).toBeInTheDocument();
    expect(
      screen.getByText('No completed PAPER trades yet.'),
    ).toBeInTheDocument();
    expect(screen.getAllByText('Ready')).not.toHaveLength(0);
    expect(screen.queryByText('Flat')).not.toBeInTheDocument();
  });

  it('shows degraded system facts without diagnostic prose', async () => {
    mocks.ready.mockResolvedValue({
      status: 'not_ready',
      service: 'atlas-api',
      checks: { database: 'unavailable' },
    });

    render(<Overview />);

    expect(await screen.findByText('Needs attention')).toBeInTheDocument();
    expect(screen.getByText('Not ready')).toBeInTheDocument();
    expect(screen.getByText('Unavailable')).toBeInTheDocument();
    expect(
      screen.queryByText(/Readiness is unavailable/),
    ).not.toBeInTheDocument();
  });

  it('keeps a failed Strategy read independent from known sections', async () => {
    mocks.listStrategies.mockRejectedValue(
      new Error('Strategy catalog offline'),
    );

    render(<Overview />);

    expect(
      await screen.findByText('Strategy catalog offline'),
    ).toBeInTheDocument();
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(screen.getByText('EUR/USD')).toBeInTheDocument();
    expect(screen.getByText('Candle Confirmation Break')).toBeInTheDocument();
    expect(screen.getAllByText('Ready')).not.toHaveLength(0);
  });

  it('keeps failed Experiments and System reads independently retryable', async () => {
    mocks.listExperiments.mockRejectedValue(
      new Error('Experiment read offline'),
    );
    mocks.ready.mockRejectedValue(new Error('System read offline'));

    render(<Overview />);

    expect(
      await screen.findByText('Experiment read offline'),
    ).toBeInTheDocument();
    expect(screen.getByText('System read offline')).toBeInTheDocument();
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(screen.getByText('EUR/USD')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Retry' })).not.toHaveLength(
      0,
    );
    expect(
      screen.queryByText('PAPER_ACTIVATION_NOT_ACTIVE'),
    ).not.toBeInTheDocument();
  });

  it('keeps broker exposure unavailable rather than implying flatness', async () => {
    mocks.paperBrokerState.mockRejectedValue(
      new Error('Current broker state is unavailable.'),
    );

    render(<Overview />);

    expect(await screen.findByText('Broker unavailable')).toBeInTheDocument();
    expect(screen.getByText('Candle Confirmation Break')).toBeInTheDocument();
    expect(screen.queryByText('No open trades')).not.toBeInTheDocument();
    expect(screen.queryByText('Flat')).not.toBeInTheDocument();
  });

  it('uses compact runtime state and keeps broker refresh read-only', async () => {
    mocks.activePaperStatus.mockResolvedValue({
      activation: {
        activationId: 'activation-1',
        lifecycleState: 'REQUESTED',
        operationalPhase: 'STARTING',
        stateChangedAt: '2026-01-01T00:00:00Z',
        stateReasonCode: 'PAPER_RUNNING',
        stateDetail: 'Current runtime status is reported.',
      },
      currentFinancialPositionState: 'FLAT_UNKNOWN',
      executionOutcome: 'NO_ACTION_REPORTED',
      reconciliationStatus: 'NOT_REPORTED',
      terminalRuntimeStateDoesNotProveFlat: true,
    });
    render(<Overview />);

    expect(
      await screen.findByText('Approved — waiting for Atlas runtime'),
    ).toBeInTheDocument();
    expect(screen.getByText('Starting')).toBeInTheDocument();
    expect(
      screen.queryByText('PAPER_ACTIVATION_NOT_ACTIVE'),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Trade 7')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Refresh broker state' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Buy|Sell|Activate|Reconcile/),
    ).not.toBeInTheDocument();
  });

  it.each([
    ['BLOCKED', 'Blocked'],
    ['FAILED', 'Failed'],
  ])('does not style compact %s as success', async (lifecycle, label) => {
    mocks.activePaperStatus.mockResolvedValue({
      activation: {
        activationId: 'activation-1',
        lifecycleState: lifecycle,
        operationalPhase: lifecycle,
      },
    });
    render(<Overview />);

    const lifecycleStatus = await screen.findByText(label, {
      selector: 'p.status',
    });
    expect(lifecycleStatus).toHaveClass('status-danger');
    expect(lifecycleStatus).not.toHaveClass('status-success');
  });
});
