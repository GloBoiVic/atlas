import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getExperiment: vi.fn(),
  getEquity: vi.fn(),
  listTrades: vi.fn(),
  getTrade: vi.fn(),
  createChart: vi.fn(),
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
  },
  ApiTransportTimeoutError: class ApiTransportTimeoutError extends Error {},
}));
vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 0 },
  LineSeries: {},
  CandlestickSeries: {},
  createChart: mocks.createChart,
}));
import {
  ExperimentStatusPage,
  TradeDetailPage,
} from '../components/experiment-workflow';

function chartApi() {
  const remove = vi.fn();
  const chart = {
    addSeries: vi.fn(() => ({ setData: vi.fn(), createPriceLine: vi.fn() })),
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
});

afterEach(() => cleanup());

describe('completed Experiment result states', () => {
  it('renders VALUE, INFINITE, unavailable reasons, zero-Trade messaging, disclosures, and both charts', async () => {
    mocks.getExperiment.mockResolvedValue(completed('0'));
    const { unmount } = render(<ExperimentStatusPage />);

    expect(await screen.findByText('No Trades')).toBeInTheDocument();
    expect(screen.getByText('0.125')).toBeInTheDocument();
    expect(screen.getByText('∞')).toBeInTheDocument();
    expect(screen.getAllByText('Unavailable')).toHaveLength(3);
    expect(screen.getAllByText('ZERO_TRADES')).toHaveLength(3);
    expect(screen.getByText(/FINANCING EXCLUDED/)).toBeInTheDocument();
    expect(
      screen.getByText('No executed Trades for this Experiment.'),
    ).toBeInTheDocument();
    await waitFor(() => expect(mocks.createChart).toHaveBeenCalledTimes(2));

    expect(screen.getByRole('heading', { name: 'Trades' })).toBeInTheDocument();
    unmount();
    expect(mocks.createChart.mock.results[0].value.remove).toHaveBeenCalled();
  });
});

describe('terminal and persistent result states', () => {
  it('keeps failed Experiments fail-closed with no result hierarchy', async () => {
    mocks.getExperiment.mockResolvedValue({
      ...completed('2'),
      status: 'FAILED',
      failure: {
        category: 'DATA',
        code: 'MISSING_DATA',
        detail: 'The snapshot has a gap.',
      },
    });
    render(<ExperimentStatusPage />);

    expect(
      await screen.findByText('No trustworthy full result was created.'),
    ).toBeInTheDocument();
    expect(screen.getByText('The snapshot has a gap.')).toBeInTheDocument();
    expect(screen.queryByText('Result')).not.toBeInTheDocument();
    expect(screen.queryByText('Equity curve')).not.toBeInTheDocument();
  });

  it('keeps RUNNING status persistent without exposing partial result facts', async () => {
    mocks.getExperiment.mockResolvedValue({
      ...completed('1'),
      status: 'RUNNING',
    });
    render(<ExperimentStatusPage />);

    expect(
      await screen.findByText(/Atlas is running the deterministic simulation/),
    ).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.queryByText('Equity curve')).not.toBeInTheDocument();
  });
});

describe('focused Trade detail', () => {
  it('renders immutable chart context, rationale, lineage, ambiguity, and omitted-range disclosure', async () => {
    mocks.getTrade.mockResolvedValue({
      summary: {
        sequence_number: 1,
        direction: 'LONG',
        opened_at: '2024-01-01T01:00:00Z',
        closed_at: '2024-01-01T03:00:00Z',
        entry_price: '1.10000',
        exit_price: '1.10100',
        net_pnl: '10.00',
        r_multiple: '1.2',
        exit_reason: 'TARGET',
        ambiguous: true,
      },
      initial_stop: '1.09900',
      target: '1.10100',
      financing_disclosure: 'FINANCING EXCLUDED',
      rationale: {
        fields: [
          ['reference_time', '2024-01-01T00:30:00Z'],
          ['reason', 'engulfing confirmation'],
        ],
      },
      risks: [
        { phase: 'PRE_SUBMISSION', outcome: 'APPROVED', stop_price: '1.09900' },
      ],
      orders: [{ status: 'FILLED', events: [{ event: 'ORDER_SUBMITTED' }] }],
      fills: [{ price: '1.10000', fee: '0.01' }],
      chart: {
        candles: [
          {
            time: '2024-01-01T01:00:00Z',
            open: '1.1',
            high: '1.102',
            low: '1.099',
            close: '1.101',
            ema: '1.1005',
          },
        ],
        omitted_range: {
          start: '2024-01-01T00:00:00Z',
          end: '2024-01-01T01:00:00Z',
        },
      },
    });
    render(<TradeDetailPage />);

    expect(
      await screen.findByRole('heading', { name: 'Trade 1' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Ambiguous intrabar resolution/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Chart omits a range/)).toBeInTheDocument();
    expect(screen.getByText('TradeIntent rationale')).toBeInTheDocument();
    expect(screen.getByText('Execution lineage')).toBeInTheDocument();
    expect(screen.getByText('FINANCING EXCLUDED')).toBeInTheDocument();
    expect(mocks.createChart).toHaveBeenCalled();
    expect(
      mocks.createChart.mock.results[0].value.addSeries,
    ).toHaveBeenCalledTimes(2);
  });
});
