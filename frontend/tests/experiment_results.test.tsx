import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getExperiment: vi.fn(),
  getEquity: vi.fn(),
  listTrades: vi.fn(),
  getTrade: vi.fn(),
  getPriceAnalysis: vi.fn(),
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
    getPriceAnalysis: mocks.getPriceAnalysis,
  },
  ApiTransportTimeoutError: class ApiTransportTimeoutError extends Error {},
}));
vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 0 },
  LineSeries: {},
  CandlestickSeries: {},
  createSeriesMarkers: vi.fn(),
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
  strategy: {
    displayName: 'EMA Sweep Confirmation Break v1',
  },
  createdAt: '2024-01-03T00:00:00Z',
  tradingStart: '2024-01-01T00:00:00Z',
  tradingEnd: '2024-01-02T00:00:00Z',
  startingCapital: '10000',
  riskPerTrade: '0.01',
  modelVersion: 'PHASE4_HISTORICAL_EXECUTION_V1',
  resultSchemaVersion: 'PHASE5_EXPERIMENT_RESULT_V1',
  resultQuality: { schema: 'ATLAS_RESULT_QUALITY_V1', value: 'DETERMINED' },
  provenance: {
    snapshotSchema: 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2',
    analyticalSeries: 'PERSISTED_NATIVE_M15_MID',
    executionSeries: 'SPARSE_PROVIDER_M1_BID_ASK',
  },
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

describe('completed Experiment result states', () => {
  it('renders VALUE, INFINITE, unavailable reasons, zero-Trade messaging, disclosures, and both charts', async () => {
    mocks.getExperiment.mockResolvedValue(completed('0'));
    const { unmount } = render(<ExperimentStatusPage />);

    expect(await screen.findByText('No Trades')).toBeInTheDocument();
    expect(
      screen.getAllByText('EMA Sweep Confirmation Break v1').length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText('EMA Sweep Engulfing')).not.toBeInTheDocument();
    expect(screen.getByText('12.50%')).toBeInTheDocument();
    expect(screen.getByText('∞')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(screen.getAllByText('ZERO_TRADES')).toHaveLength(3);
    expect(screen.getByText(/FINANCING EXCLUDED/)).toBeInTheDocument();
    expect(screen.getByText(/Native M15 MID analysis/)).toBeInTheDocument();
    expect(
      screen.getByText(/Result schema PHASE5_EXPERIMENT_RESULT_V1/),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No executed Trades for this Experiment.'),
    ).toBeInTheDocument();
    expect(
      await screen.findByText('No trades were generated in this period.'),
    ).toBeInTheDocument();
    await waitFor(() => expect(mocks.createChart).toHaveBeenCalledTimes(2));
    const priceChartOptions = mocks.createChart.mock.calls.find(
      ([, options]) => options?.timeScale?.tickMarkFormatter,
    )?.[1];
    expect(priceChartOptions.localization.timeFormatter(1704068100)).toContain(
      'CST',
    );
    expect(mocks.getPriceAnalysis).toHaveBeenCalledWith('experiment-1');

    expect(screen.getByRole('heading', { name: 'Trades' })).toBeInTheDocument();
    unmount();
    expect(mocks.createChart.mock.results[0].value.remove).toHaveBeenCalled();
  });

  it('renders trade facts and a persistent truncation disclosure', async () => {
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
    expect(await screen.findByText(/Chart truncated/)).toBeInTheDocument();
    expect(
      screen.getByText(/M15 candles and 1 Trades omitted/),
    ).toBeInTheDocument();
    expect(mocks.getPriceAnalysis).toHaveBeenCalledWith('experiment-1');
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
