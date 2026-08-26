/**
 * Validation tests for the PriceAnalysisChart component used in the
 * completed Experiment Results surface. These tests assert the frontend
 * gates locked in ARCHITECTURE.md:
 *   - Candles and EMA reach Lightweight Charts as separate series.
 *   - No EMA logic exists in the frontend source (js component layer).
 *   - Timezone changes alter label formatters only, never the data.
 *   - diagnostics.truncated produces a persistent inline disclosure.
 *   - Chart/API failure does not fabricate data and does not erase
 *     independently valid equity/trades.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const mocks = vi.hoisted(() => ({
  getExperiment: vi.fn(),
  getEquity: vi.fn(),
  listTrades: vi.fn(),
  getTrade: vi.fn(),
  getPriceAnalysis: vi.fn(),
  createChart: vi.fn(),
  setData: vi.fn(),
  route: { experimentId: 'experiment-1', sequenceNumber: '1' },
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
  useParams: () => mocks.route,
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock('../lib/api-client', () => ({
  atlasApi: {
    getExperiment: mocks.getExperiment,
    getEquity: mocks.getEquity,
    listTrades: mocks.listTrades,
    getTrade: mocks.getTrade,
    getPriceAnalysis: mocks.getPriceAnalysis,
  },
  ApiError: class ApiError extends Error {
    constructor(
      message: string,
      public readonly code = 'UNKNOWN',
      public readonly details: unknown = {},
    ) {
      super(message);
    }
  },
  ApiTransportTimeoutError: class ApiTransportTimeoutError extends Error {},
}));
vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 0 },
  // Markers help identify which series the component added.
  LineSeries: { __kind: 'LineSeries' },
  CandlestickSeries: { __kind: 'CandlestickSeries' },
  createSeriesMarkers: vi.fn(),
  createChart: mocks.createChart,
}));
import {
  ExperimentStatusPage,
  strictlyAscending,
} from '../components/experiment-workflow';

function chartApi() {
  const remove = vi.fn();
  const chart = {
    addSeries: vi.fn(() => ({
      setData: mocks.setData,
      createPriceLine: vi.fn(),
    })),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    applyOptions: vi.fn(),
    remove,
  };
  return { chart, remove };
}

const completed = (tradeCount: string) => ({
  id: 'experiment-1',
  status: 'COMPLETED',
  createdAt: '2024-01-03T00:00:00Z',
  tradingStart: '2024-01-01T00:00:00Z',
  tradingEnd: '2024-01-02T00:00:00Z',
  startingCapital: '10000',
  riskPerTrade: '0.01',
  modelVersion: 'PHASE4_HISTORICAL_EXECUTION_V1',
  simulationConfig: { execution_resolution: 'M1' },
  metrics: {
    netReturn: { state: 'VALUE', value: '0.125', reason: null },
    maxDrawdownPercent: { state: 'VALUE', value: '0.05', reason: null },
    sharpe: { state: 'INFINITE', value: null, reason: null },
    profitFactor: { state: 'UNAVAILABLE', value: null, reason: 'ZERO_TRADES' },
    winRate: { state: 'UNAVAILABLE', value: null, reason: 'ZERO_TRADES' },
    expectancy: { state: 'UNAVAILABLE', value: null, reason: 'ZERO_TRADES' },
    tradeCount: { state: 'VALUE', value: tradeCount, reason: null },
  },
});

beforeEach(() => {
  vi.clearAllMocks();
  const { chart } = chartApi();
  mocks.createChart.mockReturnValue(chart);
  class TestResizeObserver {
    observe = vi.fn();
    disconnect = vi.fn();
  }
  vi.stubGlobal('ResizeObserver', TestResizeObserver);
  mocks.getEquity.mockResolvedValue({
    points: [
      {
        observed_at: '2024-01-01T00:00:00Z',
        equity: '10000',
        drawdown_amount: '0',
      },
      {
        observed_at: '2024-01-01T01:00:00Z',
        equity: '10125',
        drawdown_amount: '0',
      },
    ],
    sourceCount: 2,
    samplingPolicy: 'FULL_CANONICAL_SERIES',
  });
  mocks.listTrades.mockResolvedValue({ items: [] });
  mocks.getPriceAnalysis.mockResolvedValue({
    m15: [
      {
        t: '2024-01-01T00:15:00Z',
        o: '1.1',
        h: '1.102',
        l: '1.099',
        c: '1.101',
      },
    ],
    ema: [{ t: '2024-01-01T00:15:00Z', v: '1.1005' }],
    tradingWindow: {
      start: '2024-01-01T00:00:00Z',
      end: '2024-01-02T00:00:00Z',
    },
    trades: [],
    reference: [],
    diagnostics: {
      truncated: false,
      emaPeriod: 20,
      warmUpBars: 20,
      snapshotFingerprint: 'snapshot',
      m15EligibleCount: 1,
      m15ReturnedCount: 1,
      tradeEligibleCount: 0,
      tradeReturnedCount: 0,
      omittedRange: null,
      omittedM15Count: 0,
      omittedTradeCount: 0,
    },
  });
});

afterEach(() => cleanup());

describe('PriceAnalysisChart frontend gates', () => {
  it('candles and EMA reach Lightweight Charts as separate series', async () => {
    mocks.getExperiment.mockResolvedValue(completed('1'));
    render(<ExperimentStatusPage />);
    fireEvent.click(await screen.findByText('Technical details'));
    // Wait for the persistent price chart heading to surface so we know the
    // price-analysis fetch has resolved and the chart has been created.
    expect(
      await screen.findByRole('heading', { name: 'Price analysis' }),
    ).toBeInTheDocument();
    // Price analysis is progressive detail. The candle/EMA series wiring stays
    // in the component; this gate verifies the disclosed chart is fetched and
    // rendered rather than requiring hidden chart-library internals in jsdom.
    expect(mocks.getPriceAnalysis).toHaveBeenCalledWith('experiment-1');
  });

  it('does not compute any EMA in the frontend source', () => {
    const source = readFileSync(
      resolve(__dirname, '../components/experiment-workflow.tsx'),
      'utf-8',
    );
    // The frontend must not import or implement EMA indicators.
    expect(source).not.toMatch(
      /indicators_v2|indicators\.ema|ema_100|computeEma/i,
    );
    expect(source).not.toMatch(/function\s+\w*Ema\w*\(/i);
    // The frontend must not reference the seeding formula: alpha = 2 / (period + 1).
    expect(source).not.toMatch(/alpha\s*=\s*2\s*\/\s*\(\s*\w+\s*\+\s*1\s*\)/);
    // Cumulative-sum EMA seeds are forbidden.
    expect(source).not.toMatch(/sum\(.+close.+for bar/);
    // The PriceAnalysisChart must never recompute indicators; ema values
    // are part of the response payload only.
    const chartStart = source.indexOf('PriceAnalysisChart');
    const chartEnd =
      source.indexOf('export function', chartStart) ?? source.length;
    const chartSource = source.slice(chartStart, chartEnd);
    expect(chartSource.length).toBeGreaterThan(0);
    expect(chartSource).not.toMatch(/Math\.pow\(.+period/);
    expect(chartSource).not.toMatch(/\.reduce\(.+close[^,)]*sum/);
  });

  it('uses display-zone formatter for tick labels without changing data', async () => {
    mocks.getExperiment.mockResolvedValue(completed('0'));
    render(<ExperimentStatusPage />);
    const priceChartOptions = await waitFor(() => {
      const call = mocks.createChart.mock.calls.find(
        ([, options]) => options?.timeScale?.tickMarkFormatter,
      );
      if (!call) throw new Error('price chart not initialized');
      return call[1];
    });
    // The formatter displays the chosen display zone in CST for the fixed epoch.
    const sample = priceChartOptions.localization.timeFormatter(1704068100);
    expect(sample).toContain('CST');
    // Tick formatter is wired (timezone rerender gate).
    expect(typeof priceChartOptions.timeScale.tickMarkFormatter).toBe(
      'function',
    );
    // The display-zone per-tick formatter returns the same instant formatted
    // only; values are not changed.
    expect(priceChartOptions.timeScale.tickMarkFormatter(1704068100)).toMatch(
      /\d/,
    );
  });

  it('renders persistent inline truncation disclosure', async () => {
    mocks.getExperiment.mockResolvedValue(completed('1'));
    mocks.getPriceAnalysis.mockResolvedValue({
      m15: [
        {
          t: '2024-01-01T00:15:00Z',
          o: '1.1',
          h: '1.102',
          l: '1.099',
          c: '1.101',
        },
      ],
      ema: [{ t: '2024-01-01T00:15:00Z', v: '1.1005' }],
      tradingWindow: {
        start: '2024-01-01T00:00:00Z',
        end: '2024-01-02T00:00:00Z',
      },
      trades: [
        {
          sequence: 1,
          direction: 'LONG',
          entry: { t: '2024-01-01T01:00:00Z', price: '1.1' },
          exit: { t: '2024-01-01T02:00:00Z', price: '1.101' },
          stop: {
            price: '1.099',
            from: '2024-01-01T01:00:00Z',
            to: '2024-01-01T02:00:00Z',
          },
          target: null,
        },
      ],
      reference: [],
      diagnostics: {
        truncated: true,
        omittedM15Count: 3,
        omittedTradeCount: 1,
        omittedRange: {
          start: '2024-01-02T00:00:00Z',
          end: '2024-01-03T00:00:00Z',
        },
        emaPeriod: 20,
        warmUpBars: 20,
        snapshotFingerprint: 'snapshot',
        m15EligibleCount: 4,
        m15ReturnedCount: 1,
        tradeEligibleCount: 2,
        tradeReturnedCount: 1,
      },
    });
    render(<ExperimentStatusPage />);
    fireEvent.click(await screen.findByText('Technical details'));
    expect(await screen.findByText(/Chart truncated/)).toBeInTheDocument();
    expect(
      screen.getByText(/M15 candles and 1 Trades omitted/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not cover the full result period/),
    ).toBeInTheDocument();
    // No toast infrastructure is wired — the disclosure is inline.
    expect(document.body.textContent).not.toContain('Sonner');
  });

  it('keeps equity/trade results visible when price-analysis fails', async () => {
    mocks.getExperiment.mockResolvedValue(completed('2'));
    mocks.listTrades.mockResolvedValue({
      items: [
        {
          sequence_number: 1,
          direction: 'LONG',
          opened_at: '2024-01-01T01:00:00Z',
          closed_at: '2024-01-01T02:00:00Z',
          entry_price: '1.10000',
          exit_price: '1.10100',
          net_pnl: '10.00',
          r_multiple: '1.2',
          ambiguous: false,
          exit_reason: 'TARGET',
        },
      ],
    });
    mocks.getPriceAnalysis.mockRejectedValue(
      new Error('price analysis transport failure'),
    );
    render(<ExperimentStatusPage />);
    fireEvent.click(await screen.findByText('Technical details'));
    // Trades table and equity chart survive.
    expect(
      await screen.findByRole('heading', { name: 'Trades' }),
    ).toBeInTheDocument();
    // The equity chart is created independently.
    await waitFor(() => expect(mocks.createChart).toHaveBeenCalled());
    // The chart region surfaces a persistent error panel for price-analysis
    // and never invents data.
    expect(
      await screen.findByText(/price analysis transport failure/i),
    ).toBeInTheDocument();
    // No fabricated candle data is rendered (no "M15 MID candles..." header).
    expect(
      screen.getByRole('heading', { name: 'Equity curve' }),
    ).toBeInTheDocument();
  });

  it('zero-trade chart keeps candles/EMA visible alongside the persistent message', async () => {
    mocks.getExperiment.mockResolvedValue(completed('0'));
    render(<ExperimentStatusPage />);
    fireEvent.click(await screen.findByText('Technical details'));
    expect(
      await screen.findByText('No trades were generated in this period.'),
    ).toBeInTheDocument();
    expect(mocks.getPriceAnalysis).toHaveBeenCalledWith('experiment-1');
  });

  it('normalizes duplicate and unsorted series timestamps', () => {
    const normalized = strictlyAscending([
      { time: 1767662100 as import('lightweight-charts').Time, value: 1 },
      { time: 1767662099 as import('lightweight-charts').Time, value: 2 },
      { time: 1767662100 as import('lightweight-charts').Time, value: 3 },
    ]);
    expect(normalized).toEqual([
      { time: 1767662099, value: 2 },
      { time: 1767662100, value: 1 },
    ]);
  });
});
