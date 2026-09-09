import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  paperCapability: vi.fn(),
  paperBrokerState: vi.fn(),
  activePaperStatus: vi.fn(),
}));

vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({
    timeZone: 'America/New_York',
    setTimeZone: vi.fn(),
  }),
}));
vi.mock('../lib/api-client', () => ({ atlasApi: mocks }));

import { PaperStatus } from '../components/paper-status';

const capability = {
  provider: 'OANDA Practice',
  environment: 'practice',
  instrument: 'EUR/USD',
  available: true,
  reasonCode: null,
};

const activeStatus = {
  activation: {
    activationId: 'activation-1',
    lifecycleState: 'ACTIVE',
    operationalPhase: 'RUNNING',
    stateChangedAt: '2026-01-01T00:00:00Z',
    stateReasonCode: 'PAPER_RUNNING',
    stateDetail: 'Current runtime status is reported.',
  },
  currentFinancialPositionState: 'FLAT_UNKNOWN',
  executionOutcome: 'NO_ACTION_REPORTED',
  reconciliationStatus: 'NOT_REPORTED',
  terminalRuntimeStateDoesNotProveFlat: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.paperCapability.mockResolvedValue(capability);
  mocks.paperBrokerState.mockResolvedValue({
    provider: 'OANDA',
    environment: 'PRACTICE',
    accountCurrency: 'USD',
    openTrades: [],
  });
  mocks.activePaperStatus.mockResolvedValue(null);
});
afterEach(() => cleanup());

describe('PAPER read-only surface', () => {
  it('represents PAPER_ACTIVATION_NOT_ACTIVE as current-state empty and exposes no mutation controls', async () => {
    render(<PaperStatus />);

    expect(
      await screen.findByText(/No active PAPER activation reported/),
    ).toBeInTheDocument();
    expect(screen.getByText('PAPER_ACTIVATION_NOT_ACTIVE')).toBeInTheDocument();
    expect(
      screen.getByText(/does not reconstruct historical activations/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not prove broker flatness/),
    ).toBeInTheDocument();
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(screen.queryByText('EUR/USD')).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Buy|Sell|Close|SL\/TP|Activate|Stop|Reconcile/),
    ).not.toBeInTheDocument();
    // Refresh is the only allowed broker-state button
    expect(
      screen.getAllByRole('button', { name: /Refresh/ }).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it('shows only the current status facts returned by an active response', async () => {
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    render(<PaperStatus />);

    expect(await screen.findByText('ACTIVE')).toBeInTheDocument();
    expect(screen.getByText('RUNNING')).toBeInTheDocument();
    expect(screen.getByText('FLAT_UNKNOWN')).toBeInTheDocument();
    expect(screen.getByText('NO_ACTION_REPORTED')).toBeInTheDocument();
    expect(screen.getByText('NOT_REPORTED')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Terminal runtime state does not prove broker flatness.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText('activation-1')).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Buy|Sell|Close|SL\/TP|Activate|Stop/),
    ).not.toBeInTheDocument();
  });

  it('keeps capability errors independent from the current empty status', async () => {
    mocks.paperCapability.mockRejectedValue(
      new Error('PAPER capability unavailable'),
    );
    render(<PaperStatus />);

    expect(
      await screen.findByText('PAPER capability unavailable'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No active PAPER activation reported/),
    ).toBeInTheDocument();
  });

  it('keeps capability and status loading states separate', () => {
    const pending = new Promise<never>(() => undefined);
    mocks.paperCapability.mockReturnValue(pending);
    mocks.paperBrokerState.mockReturnValue(pending);
    mocks.activePaperStatus.mockReturnValue(pending);
    render(<PaperStatus />);

    expect(screen.getByText('Loading PAPER capability…')).toBeInTheDocument();
    expect(screen.getByText('Loading PAPER broker state…')).toBeInTheDocument();
    expect(screen.getByText('Loading Runtime status…')).toBeInTheDocument();
  });

  it('places broker exposure above runtime and broker before readiness', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '20',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00.123456Z',
          openPrice: '1.16188',
          currentUnits: '-390663',
          state: 'OPEN',
          unrealizedPl: '-410.20',
        },
      ],
    });
    render(<PaperStatus />);
    expect(await screen.findByText('SHORT')).toBeInTheDocument();
    expect(screen.getByText('390,663 units')).toBeInTheDocument();
    expect(screen.getByText('-$410.20')).toBeInTheDocument();
    expect(screen.getAllByText('EURUSD').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('EUR_USD')).not.toBeInTheDocument();
    expect(screen.getAllByText('OANDA Practice').length).toBeGreaterThanOrEqual(
      1,
    );
    const headings = screen.getAllByRole('heading');
    const brokerIdx = headings.findIndex((h) =>
      h.textContent?.includes('PAPER broker state'),
    );
    const runtimeIdx = headings.findIndex((h) =>
      h.textContent?.includes('Runtime status'),
    );
    expect(brokerIdx).toBeGreaterThanOrEqual(0);
    expect(runtimeIdx).toBeGreaterThanOrEqual(0);
    expect(brokerIdx).toBeLessThan(runtimeIdx);
  });

  it('renders empty broker state distinct from unavailable', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [],
    });
    render(<PaperStatus />);
    expect(
      await screen.findByText('No open broker trades.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Broker unavailable')).not.toBeInTheDocument();
  });

  it('renders unavailable broker state distinct from empty', async () => {
    mocks.paperBrokerState.mockRejectedValue(new Error('broker down'));
    render(<PaperStatus />);
    expect(await screen.findByText('Broker unavailable')).toBeInTheDocument();
    expect(
      screen.queryByText('No open broker trades.'),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Flat')).not.toBeInTheDocument();
  });

  it('refresh retries broker state GET only', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [],
    });
    render(<PaperStatus />);
    expect(
      await screen.findByText('No open broker trades.'),
    ).toBeInTheDocument();
    const refresh = screen.getAllByRole('button', { name: /Refresh/ })[0];
    expect(refresh).toBeInTheDocument();
    expect(mocks.paperBrokerState).toHaveBeenCalledTimes(1);
  });

  it('formats unrealized P/L to two decimal places', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '7',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00Z',
          openPrice: '1.10000',
          currentUnits: '1000',
          state: 'OPEN',
          unrealizedPl: '0.00001',
        },
      ],
    });
    render(<PaperStatus />);
    expect(await screen.findByText('$0.00')).toHaveClass('text-atlas-positive');
    expect(screen.getAllByText('EURUSD').length).toBeGreaterThanOrEqual(2);
  });

  it('shows multiple trades without netting', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '1',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00Z',
          openPrice: '1.1',
          currentUnits: '100',
          state: 'OPEN',
          unrealizedPl: '1.00',
        },
        {
          tradeId: '2',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:01:00Z',
          openPrice: '1.2',
          currentUnits: '-200',
          state: 'OPEN',
          unrealizedPl: '-2.00',
        },
      ],
    });
    render(<PaperStatus />);
    expect(await screen.findByText('LONG')).toBeInTheDocument();
    expect(await screen.findByText('SHORT')).toBeInTheDocument();
    expect(screen.getByText('100 units')).toBeInTheDocument();
    expect(screen.getByText('200 units')).toBeInTheDocument();
    expect(screen.getAllByText('EURUSD').length).toBeGreaterThanOrEqual(3);
  });
});
