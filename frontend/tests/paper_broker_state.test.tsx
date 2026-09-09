import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  paperBrokerState: vi.fn(),
}));

vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({
    timeZone: 'America/New_York',
    setTimeZone: vi.fn(),
  }),
}));
vi.mock('../lib/api-client', () => ({ atlasApi: mocks }));

import { PaperBrokerStateSection } from '../components/paper-broker-state';

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => cleanup());

describe('Paper broker state component', () => {
  it('renders LONG for positive units with absolute quantity', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '10',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00.123456Z',
          openPrice: '1.10000',
          currentUnits: '390663',
          state: 'OPEN',
          unrealizedPl: '10.00',
        },
      ],
    });
    render(<PaperBrokerStateSection />);
    expect(await screen.findByText('LONG')).toBeInTheDocument();
    expect(screen.getByText('390,663 units')).toBeInTheDocument();
    expect(screen.getByText('OANDA Practice')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toHaveClass('text-atlas-positive');
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(screen.queryByText('EUR_USD')).not.toBeInTheDocument();
  });

  it('renders SHORT for negative units with absolute quantity', async () => {
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
          unrealizedPl: '-746.6756',
        },
      ],
    });
    render(<PaperBrokerStateSection />);
    expect(await screen.findByText('SHORT')).toBeInTheDocument();
    expect(screen.getByText('390,663 units')).toBeInTheDocument();
    expect(screen.getByText('-$746.67')).toHaveClass('text-atlas-negative');
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(screen.queryByText('EUR_USD')).not.toBeInTheDocument();
  });

  it('renders multiple trades distinct', async () => {
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
    render(<PaperBrokerStateSection />);
    expect(await screen.findByText('LONG')).toBeInTheDocument();
    expect(screen.getByText('SHORT')).toBeInTheDocument();
    expect(screen.getByText('100 units')).toBeInTheDocument();
    expect(screen.getByText('200 units')).toBeInTheDocument();
    expect(screen.getByText('CLOSE_WHEN_TRADEABLE')).toBeInTheDocument();
    expect(screen.getAllByText('EURUSD')).toHaveLength(2);
  });

  it('shows empty inventory only for successful empty', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [],
    });
    render(<PaperBrokerStateSection />);
    expect(
      await screen.findByText('No open broker trades.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Broker unavailable')).not.toBeInTheDocument();
  });

  it('shows unavailable on error', async () => {
    mocks.paperBrokerState.mockRejectedValue(new Error('unavailable'));
    render(<PaperBrokerStateSection />);
    expect(await screen.findByText('Broker unavailable')).toBeInTheDocument();
    expect(
      screen.queryByText('No open broker trades.'),
    ).not.toBeInTheDocument();
  });

  it('uses display timezone for opened time', async () => {
    mocks.paperBrokerState.mockResolvedValue({
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
    });
    render(<PaperBrokerStateSection />);
    // New York is UTC-5 in Jan, so 08:00Z -> 03:00 EST
    const text = await screen.findByText(/Jan 5, 2026/);
    expect(text).toBeInTheDocument();
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
  });

  it('refresh triggers GET-only retry', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [],
    });
    render(<PaperBrokerStateSection />);
    expect(
      await screen.findByText('No open broker trades.'),
    ).toBeInTheDocument();
    expect(mocks.paperBrokerState).toHaveBeenCalledTimes(1);
    const btn = screen.getByRole('button', { name: /Refresh/ });
    await fireEvent.click(btn);
    // useReadResource retry increments attempt, triggers reload
    expect(
      await screen.findByText('No open broker trades.'),
    ).toBeInTheDocument();
    expect(mocks.paperBrokerState).toHaveBeenCalledTimes(2);
  });

  it('does not show mutation controls', async () => {
    mocks.paperBrokerState.mockResolvedValue({
      provider: 'OANDA',
      environment: 'PRACTICE',
      accountCurrency: 'USD',
      openTrades: [
        {
          tradeId: '7',
          instrument: 'EUR_USD',
          openTime: '2026-01-05T08:00:00Z',
          openPrice: '1.1',
          currentUnits: '100',
          state: 'OPEN',
          unrealizedPl: '1.00',
        },
      ],
    });
    render(<PaperBrokerStateSection />);
    expect(await screen.findByText('LONG')).toBeInTheDocument();
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    expect(
      screen.queryByText(/Buy|Sell|Close|Activate|Stop|Reconcile/),
    ).not.toBeInTheDocument();
  });
});
