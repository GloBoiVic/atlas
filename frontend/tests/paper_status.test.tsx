import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  class MockApiError extends Error {}
  return {
    paperCapability: vi.fn(),
    paperBrokerState: vi.fn(),
    listPaperTrades: vi.fn(),
    activePaperStatus: vi.fn(),
    paperStatus: vi.fn(),
    stopPaper: vi.fn(),
    ApiError: MockApiError,
  };
});

vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({
    timeZone: 'America/New_York',
    setTimeZone: vi.fn(),
  }),
}));
vi.mock('../lib/api-client', () => ({
  atlasApi: mocks,
  ApiError: mocks.ApiError,
}));

import {
  PaperActiveStatusSection,
  PaperStatus,
} from '../components/paper-status';

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
    strategyVersionId: 'version-1',
    strategyKey: 'ema',
    strategyVersionNumber: 2,
    riskPerTrade: '0.01',
    lifecycleState: 'RUNNING',
    operationalPhase: 'EVALUATING',
    stateChangedAt: '2026-01-01T00:00:00Z',
    stateReasonCode: 'PAPER_RUNNING',
    stateDetail: 'Current runtime status is reported.',
  },
  currentFinancialPositionState: 'FLAT_UNKNOWN',
  executionOutcome: 'NO_ACTION_REPORTED',
  reconciliationStatus: 'NOT_REPORTED',
  terminalRuntimeStateDoesNotProveFlat: true,
};

const statusAt = (lifecycleState: string, operationalPhase: string) => ({
  ...activeStatus,
  activation: {
    ...activeStatus.activation,
    lifecycleState,
    operationalPhase,
  },
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.paperCapability.mockResolvedValue(capability);
  mocks.paperBrokerState.mockResolvedValue({
    provider: 'OANDA',
    environment: 'PRACTICE',
    accountCurrency: 'USD',
    openTrades: [],
  });
  mocks.listPaperTrades.mockResolvedValue({ items: [] });
  mocks.activePaperStatus.mockResolvedValue(null);
  mocks.paperStatus.mockResolvedValue(activeStatus);
  mocks.stopPaper.mockResolvedValue({
    ...activeStatus.activation,
    lifecycleState: 'STOP_REQUESTED',
    operationalPhase: 'STOPPING',
  });
});
afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

describe('PAPER supervision surface', () => {
  it('shows the idle session state and activation CTA without broker controls', async () => {
    render(<PaperStatus />);

    expect(
      await screen.findByText('No active PAPER session'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Activate PAPER' }),
    ).toHaveAttribute('href', '/paper/activate');
    expect(
      screen.getByText(/does not reconstruct historical activations/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not prove broker flatness/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Completed PAPER trades' }),
    ).toBeInTheDocument();
    expect(mocks.listPaperTrades).toHaveBeenCalledWith({ limit: 20 });
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(screen.queryByText('EUR/USD')).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Buy|Sell|Close|SL\/TP|Reconcile/),
    ).not.toBeInTheDocument();
    // Refresh is the only allowed broker-state button
    expect(
      screen.getAllByRole('button', { name: /Refresh/ }).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it('shows only the current status facts returned by an active response', async () => {
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    render(<PaperStatus />);

    expect(await screen.findByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Evaluating Strategy')).toBeInTheDocument();
    expect(screen.getByText('ema')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
    expect(screen.getByText('1%')).toBeInTheDocument();
    expect(screen.getByText('FLAT_UNKNOWN')).toBeInTheDocument();
    expect(screen.getByText('NO_ACTION_REPORTED')).toBeInTheDocument();
    expect(screen.getByText('NOT_REPORTED')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Terminal runtime state does not prove broker flatness.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText('activation-1')).not.toBeInTheDocument();
    expect(screen.queryByText(/Buy|Sell|Close|SL\/TP/)).not.toBeInTheDocument();
  });

  it('renders active runtime concisely in compact mode', async () => {
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    render(<PaperActiveStatusSection compact />);

    expect(
      await screen.findByRole('heading', { name: 'Runtime' }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Evaluating Strategy')).toBeInTheDocument();
    expect(screen.queryByText('FLAT_UNKNOWN')).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        'Terminal runtime state does not prove broker flatness.',
      ),
    ).not.toBeInTheDocument();
  });

  it.each([
    ['REQUESTED', 'IDLE', 'Approved — waiting for Atlas runtime', 'Waiting'],
    ['STARTING', 'STARTING', 'Starting', 'Starting'],
    ['RUNNING', 'EVALUATING', 'Running', 'Evaluating Strategy'],
    ['STOP_REQUESTED', 'STOPPING', 'Stopping', 'Stopping'],
    ['STOPPED', 'STOPPING', 'Stopped', 'Stopping'],
    ['BLOCKED', 'BLOCKED', 'Blocked', 'Blocked'],
    ['FAILED', 'FAILED', 'Failed', 'Failed'],
  ])(
    'renders trader-facing %s lifecycle and phase labels',
    async (lifecycle, phase, lifecycleLabel, phaseLabel) => {
      mocks.activePaperStatus.mockResolvedValue(statusAt(lifecycle, phase));
      render(<PaperActiveStatusSection compact />);

      expect(
        (await screen.findAllByText(lifecycleLabel)).length,
      ).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(phaseLabel).length).toBeGreaterThanOrEqual(1);
    },
  );

  it('polls retained activation detail at three seconds and stops at terminal state', async () => {
    vi.useFakeTimers();
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    mocks.paperStatus.mockResolvedValue(statusAt('STOPPED', 'STOPPING'));
    render(<PaperStatus />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(mocks.paperBrokerState).toHaveBeenCalledTimes(1);
    expect(mocks.paperStatus).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2999);
    });
    expect(mocks.paperStatus).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.paperStatus).toHaveBeenCalledWith('activation-1');
    expect(mocks.paperBrokerState).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(mocks.paperStatus).toHaveBeenCalledTimes(1);
    expect(mocks.paperBrokerState).toHaveBeenCalledTimes(1);
  });

  it('repeats detail polling after an unchanged non-terminal response', async () => {
    vi.useFakeTimers();
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    mocks.paperStatus.mockResolvedValue(statusAt('RUNNING', 'EVALUATING'));
    render(<PaperActiveStatusSection />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(mocks.paperStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2999);
    });
    expect(mocks.paperStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(mocks.paperStatus).toHaveBeenCalledTimes(2);
    expect(mocks.paperStatus).toHaveBeenLastCalledWith('activation-1');
  });

  it.each(['STOPPED', 'BLOCKED', 'FAILED'])(
    'stops detail polling on %s',
    async (lifecycle) => {
      vi.useFakeTimers();
      mocks.activePaperStatus.mockResolvedValue(activeStatus);
      mocks.paperStatus.mockResolvedValue(statusAt(lifecycle, lifecycle));
      render(<PaperActiveStatusSection />);

      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(
        screen.getByRole('button', { name: 'Stop PAPER' }),
      ).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(6000);
      });

      expect(mocks.paperStatus).toHaveBeenCalledTimes(1);
    },
  );

  it('clears the detail polling timer on unmount', async () => {
    vi.useFakeTimers();
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    const { unmount } = render(<PaperActiveStatusSection />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(mocks.paperStatus).not.toHaveBeenCalled();
  });

  it('confirms STOP with the bounded runtime reason and preserves broker separation', async () => {
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    render(<PaperActiveStatusSection />);

    fireEvent.click(await screen.findByRole('button', { name: 'Stop PAPER' }));
    expect(
      screen.getByText(
        'Stopping PAPER does not close or modify broker positions or orders.',
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Close Trade/i }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Confirm stop' }));
    await waitFor(() => expect(mocks.stopPaper).toHaveBeenCalledTimes(1));
    expect(mocks.stopPaper).toHaveBeenCalledWith('activation-1', {
      reason: 'Trader requested stop from Atlas UI.',
    });
    expect(screen.getAllByText('Stopping').length).toBeGreaterThanOrEqual(1);
  });

  it('sends at most one STOP request while the confirmation is submitting', async () => {
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    mocks.stopPaper.mockReturnValue(new Promise(() => undefined));
    render(<PaperActiveStatusSection />);

    fireEvent.click(await screen.findByRole('button', { name: 'Stop PAPER' }));
    const confirm = screen.getByRole('button', { name: 'Confirm stop' });
    fireEvent.click(confirm);
    fireEvent.click(confirm);

    expect(mocks.stopPaper).toHaveBeenCalledTimes(1);
  });

  it('retains the activation ID and observes STOPPED after STOP_REQUESTED', async () => {
    vi.useFakeTimers();
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    mocks.stopPaper.mockResolvedValue(
      statusAt('STOP_REQUESTED', 'STOPPING').activation,
    );
    mocks.paperStatus.mockResolvedValue(statusAt('STOPPED', 'STOPPING'));
    render(<PaperActiveStatusSection />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Stop PAPER' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm stop' }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getAllByText('Stopping').length).toBeGreaterThanOrEqual(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(mocks.paperStatus).toHaveBeenCalledWith('activation-1');
    expect(screen.getByText('Stopped')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Stop PAPER' }),
    ).not.toBeInTheDocument();
  });

  it('resolves ambiguous STOP transport by reading detail before claiming acceptance', async () => {
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    mocks.stopPaper.mockRejectedValue(new Error('transport interrupted'));
    mocks.paperStatus.mockResolvedValue(statusAt('RUNNING', 'EVALUATING'));
    render(<PaperActiveStatusSection />);

    fireEvent.click(await screen.findByRole('button', { name: 'Stop PAPER' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm stop' }));

    expect(
      await screen.findByText(
        /Stop outcome is uncertain\. Atlas did not confirm STOP_REQUESTED or STOPPED/,
      ),
    ).toBeInTheDocument();
    expect(mocks.paperStatus).toHaveBeenCalledWith('activation-1');
    expect(
      screen.getByRole('button', { name: 'Stop PAPER' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Stopping')).not.toBeInTheDocument();
  });

  it('accepts ambiguous STOP only after detail reports STOP_REQUESTED', async () => {
    mocks.activePaperStatus.mockResolvedValue(activeStatus);
    mocks.stopPaper.mockRejectedValue(new Error('transport interrupted'));
    mocks.paperStatus.mockResolvedValue(statusAt('STOP_REQUESTED', 'STOPPING'));
    render(<PaperActiveStatusSection />);

    fireEvent.click(await screen.findByRole('button', { name: 'Stop PAPER' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm stop' }));

    expect(
      await screen.findByText(
        'Stop requested. Atlas is waiting for durable terminal session state.',
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Stop PAPER' }),
    ).not.toBeInTheDocument();
  });

  it('renders no active runtime concisely without the provider code', async () => {
    render(<PaperActiveStatusSection compact />);

    expect(await screen.findByText('No active runtime')).toBeInTheDocument();
    expect(
      screen.queryByText('PAPER_ACTIVATION_NOT_ACTIVE'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/No active PAPER session/),
    ).not.toBeInTheDocument();
  });

  it('keeps compact runtime failures concise and retryable', async () => {
    mocks.activePaperStatus.mockRejectedValue(new Error('runtime unavailable'));
    render(<PaperActiveStatusSection compact />);

    expect(await screen.findByText('Runtime unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.queryByText('runtime unavailable')).not.toBeInTheDocument();
  });

  it('keeps capability errors independent from the current empty status', async () => {
    mocks.paperCapability.mockRejectedValue(
      new Error('PAPER capability unavailable'),
    );
    render(<PaperStatus />);

    expect(
      await screen.findByText('PAPER capability unavailable'),
    ).toBeInTheDocument();
    expect(screen.getByText(/No active PAPER session/)).toBeInTheDocument();
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
    expect(
      screen.getByText('Loading completed PAPER trades…'),
    ).toBeInTheDocument();
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

  it('renders completed trade facts and only promotes exact exit causes', async () => {
    const trade = {
      strategyKey: 'ema',
      strategyName: 'EMA Sweep',
      strategyVersionNumber: 2,
      instrument: 'EUR_USD',
      direction: 'LONG',
      units: '1000',
      entryPrice: '1.10000',
      enteredAt: '2026-01-05T08:00:00Z',
      stopPrice: '1.09500',
      targetPrice: '1.11000',
      initialRisk: '0.00500',
      closedAt: '2026-01-05T09:00:00Z',
      averageClosePrice: '1.11000',
      realizedPl: '12.34',
      financing: '-0.10',
      dividendAdjustment: '0.25',
      exitCause: 'TAKE_PROFIT',
    };
    mocks.listPaperTrades.mockResolvedValue({
      items: [
        trade,
        {
          ...trade,
          direction: 'SHORT',
          realizedPl: '-7.89',
          exitCause: 'STOP_LOSS',
        },
        { ...trade, exitCause: 'MARKET_CLOSE' },
        { ...trade, exitCause: 'MARGIN_CLOSEOUT' },
        { ...trade, exitCause: 'OTHER' },
        { ...trade, exitCause: 'UNRESOLVED' },
        { ...trade, exitCause: 'MULTIPLE' },
        { ...trade, exitCause: null },
      ],
    });
    render(<PaperStatus />);

    expect(await screen.findByText('Target hit')).toBeInTheDocument();
    expect(screen.getByText('Stopped out')).toBeInTheDocument();
    expect(screen.getByText('Market close')).toBeInTheDocument();
    expect(screen.getByText('Margin closeout')).toBeInTheDocument();
    expect(screen.getByText('Other broker close')).toBeInTheDocument();
    expect(screen.getAllByText('Exit cause unavailable')).toHaveLength(3);
    expect(screen.getAllByText('LONG').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SHORT').length).toBeGreaterThan(0);
    expect(screen.getAllByText('+$12.34').length).toBeGreaterThan(0);
    expect(screen.getByText('-$7.89')).toBeInTheDocument();
    expect(screen.getAllByText('-$0.10')).toHaveLength(8);
    expect(screen.getAllByText('+$0.25')).toHaveLength(8);
    expect(screen.getAllByText('+$0.01')).toHaveLength(8);
    expect(screen.queryByText('0.00500')).not.toBeInTheDocument();
    expect(screen.getAllByText('1.09500')).toHaveLength(8);
    expect(screen.getAllByText('1.11000').length).toBeGreaterThanOrEqual(8);
    expect(
      screen.getAllByText(/Jan 5, 2026, 3:00 AM EST/).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText('MULTIPLE')).not.toBeInTheDocument();
    expect(screen.queryByText('UNRESOLVED')).not.toBeInTheDocument();
    expect(screen.queryByText('TAKE_PROFIT')).not.toBeInTheDocument();
  });

  it('keeps history failures non-destructive and retryable', async () => {
    mocks.listPaperTrades.mockRejectedValue(new Error('provider details'));
    render(<PaperStatus />);

    expect(
      await screen.findByText('Completed PAPER trades are unavailable.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'PAPER' })).toBeInTheDocument();
    expect(screen.queryByText('provider details')).not.toBeInTheDocument();
  });
});
