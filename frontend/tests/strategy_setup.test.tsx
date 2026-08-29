import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  configurationOptions: vi.fn(),
  historicalCapability: vi.fn(),
  activeHistoricalLoad: vi.fn(),
  validateCoverage: vi.fn(),
  historicalLoadStatus: vi.fn(),
  createHistoricalLoad: vi.fn(),
  createExperiment: vi.fn(),
}));

vi.mock('../components/app-shell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams('strategyVersionId=selected-v2'),
  useParams: () => ({}),
}));
vi.mock('../lib/api-client', async () => {
  class MockApiError extends Error {
    status = 422;
    code = 'TEST';
    details = {};
  }
  return {
    atlasApi: mocks,
    ApiError: MockApiError,
    ApiTransportTimeoutError: class extends Error {},
    ApiUnavailableError: class extends Error {},
  };
});
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }));

import { ExperimentForm } from '../components/experiments/experiment-setup';

const options = {
  strategyVersions: [
    {
      id: 'selected-v2',
      name: 'EMA Sweep Confirmation Break',
      displayName: 'EMA Sweep Confirmation Break v2',
      version: 2,
      parameterSchema: [],
      requiredHistoricalContextBars: 200,
      executionAvailable: true,
      marketRequirements: {
        instrument: 'EUR/USD',
        resolution: 'M15',
        priceComponent: 'MID',
        requiredHistoricalContextBars: 200,
        completedOnly: true,
      },
    },
    {
      id: 'retained-v1',
      displayName: 'Legacy v1',
      version: 1,
      parameterSchema: [],
      requiredHistoricalContextBars: 100,
      executionAvailable: false,
    },
  ],
  datasetSnapshots: [
    {
      id: 'snapshot-1',
      coverageStart: '2024-01-01T00:00:00Z',
      coverageEnd: '2024-02-01T00:00:00Z',
      integrity: { barCount: 1000 },
    },
  ],
};

describe('Experiment setup workstation stages', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.configurationOptions.mockResolvedValue(options);
    mocks.historicalCapability.mockResolvedValue({ available: true });
    mocks.activeHistoricalLoad.mockResolvedValue(null);
    mocks.validateCoverage.mockResolvedValue({
      valid: false,
      blockingReasons: [],
    });
  });

  it('honors a StrategyVersion handoff and presents the four stages in order', async () => {
    render(<ExperimentForm />);

    const strategySelect = await screen.findByRole('combobox', {
      name: 'StrategyVersion',
    });
    expect(strategySelect).toHaveValue('selected-v2');
    const headings = [
      screen.getByText('1 · StrategyVersion'),
      screen.getByText('2 · Requested period & data readiness'),
      screen.getByText('3 · Strategy & risk configuration'),
      screen.getByText('4 · Review & run Experiment'),
    ];
    expect(headings[0].compareDocumentPosition(headings[1])).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(headings[1].compareDocumentPosition(headings[2])).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(headings[2].compareDocumentPosition(headings[3])).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(
      screen.getByRole('button', { name: 'Run Experiment' }),
    ).toBeDisabled();
    expect(
      screen.getByText(/native M15 MID and sparse M1 BID\/ASK/),
    ).toBeInTheDocument();
    expect(screen.getByText('EUR/USD', { exact: true })).toBeInTheDocument();
    expect(screen.getByText('M15 MID', { exact: true })).toBeInTheDocument();
  });

  it('gives snapshots stable labels from coverage facts and blocks ambiguity', async () => {
    mocks.configurationOptions.mockResolvedValue({
      ...options,
      datasetSnapshots: [
        options.datasetSnapshots[0],
        {
          id: 'snapshot-2',
          coverageStart: '2024-02-01T00:00:00Z',
          coverageEnd: '2024-03-01T00:00:00Z',
          snapshotSchema: 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2',
          integrity: {},
        },
        {
          id: 'snapshot-ambiguous',
          coverageStart: '2024-01-01T00:00:00Z',
          coverageEnd: '2024-02-01T00:00:00Z',
          integrity: { barCount: 1000 },
        },
      ],
    });
    render(<ExperimentForm />);

    const snapshotSelect = (await screen.findAllByRole('combobox'))[1];
    expect(snapshotSelect).toHaveValue('snapshot-2');
    const snapshotOptions = Array.from(
      snapshotSelect.querySelectorAll('option'),
    );
    expect(snapshotOptions.map((option) => option.textContent)).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/Feb 1, 2024.*Mar 1, 2024/),
        expect.stringMatching(/ambiguous snapshot facts/),
      ]),
    );
    expect(
      snapshotOptions.find((option) => option.value === 'snapshot-ambiguous'),
    ).toBeDisabled();
    expect(
      screen.getByText(
        /Some snapshots are unavailable because their visible coverage facts are identical/,
      ),
    ).toBeInTheDocument();
  });

  it('keeps a failed historical load visible and blocks creation', async () => {
    mocks.activeHistoricalLoad.mockResolvedValue({
      id: 'load-failed',
      status: 'FAILED',
      failure: { reason: 'Provider did not return complete data' },
    });
    render(<ExperimentForm />);

    expect(
      await screen.findByText(/Load failed\. Valid partial bars may remain/),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Run Experiment' }),
      ).toBeDisabled(),
    );
  });

  it('renders the selected StrategyVersion schema and market pip requirement', async () => {
    mocks.configurationOptions.mockResolvedValue({
      ...options,
      strategyVersions: [
        {
          ...options.strategyVersions[0],
          parameterSchema: [
            {
              key: 'confirmation_bars',
              label: 'Confirmation bars',
              type: 'integer',
              default: 2,
              nullable: false,
              min: 1,
              max: 3,
              description: 'Consecutive breaks',
              allowedValues: [],
            },
            {
              key: 'stop_buffer_pips',
              label: 'Stop buffer (pips)',
              type: 'decimal',
              default: '20',
              nullable: false,
              min: '1',
              max: '100',
              description: 'Absolute stop buffer',
              allowedValues: [],
            },
          ],
          marketRequirements: {
            ...options.strategyVersions[0].marketRequirements,
            pipSize: '0.0001',
          },
        },
      ],
    });
    render(<ExperimentForm />);

    expect(await screen.findByText('Confirmation bars')).toBeInTheDocument();
    expect(screen.getByText('Stop buffer (pips)')).toBeInTheDocument();
    expect(screen.getByText('0.0001')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2')).toBeInTheDocument();
    expect(screen.getByDisplayValue('20')).toBeInTheDocument();
  });
});
