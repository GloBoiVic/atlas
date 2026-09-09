import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  paperCapability: vi.fn(),
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
  mocks.activePaperStatus.mockResolvedValue(null);
});
afterEach(() => cleanup());

describe('PAPER read-only surface', () => {
  it('represents PAPER_ACTIVATION_NOT_ACTIVE as current-state empty and exposes no controls', async () => {
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
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(
      screen.queryByText(/Buy|Sell|Close|SL\/TP|Activate|Stop|Reconcile/),
    ).not.toBeInTheDocument();
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
    expect(screen.queryAllByRole('button')).toHaveLength(0);
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
    mocks.activePaperStatus.mockReturnValue(pending);
    render(<PaperStatus />);

    expect(screen.getByText('Loading PAPER capability…')).toBeInTheDocument();
    expect(
      screen.getByText('Loading current PAPER status…'),
    ).toBeInTheDocument();
  });
});
