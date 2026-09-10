import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const push = vi.fn();
const mocks = vi.hoisted(() => ({
  listStrategies: vi.fn(),
  getStrategy: vi.fn(),
  paperCapability: vi.fn(),
  activePaperStatus: vi.fn(),
  paperBrokerState: vi.fn(),
  activatePaper: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));
vi.mock('../lib/api-client', async () => {
  class MockApiError extends Error {
    status = 409;
    code = 'PAPER_ACTIVATION_ALREADY_PRESENT';
    details = {};
  }
  return { atlasApi: mocks, ApiError: MockApiError };
});

import { PaperActivation } from '../components/paper-activation';

const catalog = {
  items: [
    {
      strategyKey: 'ema-sweep',
      name: 'EMA Sweep Confirmation Break',
      description: 'A completed-bar confirmation methodology.',
      latestVersion: {
        id: 'ema-v2',
        versionNumber: 2,
        displayName: 'EMA Sweep Confirmation Break v2',
      },
      versionCount: 2,
      experimentCount: 3,
      lastExperimentAt: null,
    },
  ],
};

const detail = {
  strategyKey: 'ema-sweep',
  name: 'EMA Sweep Confirmation Break',
  description: 'A completed-bar confirmation methodology.',
  versionCount: 2,
  experimentCount: 3,
  lastExperimentAt: null,
  versions: [
    {
      id: 'ema-v2',
      displayName: 'EMA Sweep Confirmation Break v2',
      versionNumber: 2,
      implementationKey: 'ema-sweep-v2',
      sourceFingerprint: 'fingerprint',
      createdAt: '2026-01-01T00:00:00Z',
      gitSha: null,
      parameterSchema: [
        {
          key: 'confirmation_bars',
          label: 'Confirmation bars',
          type: 'integer',
          default: 2,
          nullable: false,
          min: 1,
          max: 3,
        },
        {
          key: 'entry_mode',
          label: 'Entry mode',
          type: 'enum',
          default: 'close',
          nullable: false,
          allowedValues: ['close', 'break'],
        },
      ],
      contextTimeframes: ['M15'],
      timeframe: 'M15',
      requiredHistoricalContextBars: 200,
      stateSchemaVersion: 1,
      capabilities: ['PAPER'],
      experimentCount: 3,
      lastUsedAt: null,
      executionAvailable: true,
      unavailableReason: null,
      marketRequirements: {
        instrument: 'EUR/USD',
        resolution: 'M15',
        priceComponent: 'MID',
        requiredHistoricalContextBars: 200,
        completedOnly: true,
      },
      methodology: { summary: 'Sweep, confirm, and enter on completed bars.' },
    },
    {
      id: 'ema-v1',
      displayName: 'EMA Sweep Confirmation Break v1',
      versionNumber: 1,
      implementationKey: 'ema-sweep-v1',
      sourceFingerprint: 'old-fingerprint',
      createdAt: '2025-01-01T00:00:00Z',
      gitSha: null,
      parameterSchema: [],
      contextTimeframes: ['M15'],
      timeframe: 'M15',
      requiredHistoricalContextBars: 100,
      stateSchemaVersion: 1,
      capabilities: [],
      experimentCount: 1,
      lastUsedAt: null,
      executionAvailable: false,
      unavailableReason: 'Implementation is not registered locally.',
      marketRequirements: {
        instrument: 'EUR/USD',
        resolution: 'M15',
        priceComponent: 'MID',
        requiredHistoricalContextBars: 100,
        completedOnly: true,
      },
      methodology: { summary: 'Retained historical version.' },
    },
  ],
};

const capability = {
  provider: 'OANDA',
  environment: 'PRACTICE',
  baseCurrency: 'USD',
  instrument: 'EUR/USD',
  analyticalResolution: 'M15',
  analyticalPriceComponent: 'MID',
  pollIntervalSeconds: 15,
  tokenConfigured: true,
  accountConfigured: true,
  configuredAccountId: 'secret-provider-account-id',
  available: true,
  reasonCode: null,
  activationRequired: true,
};

const broker = {
  provider: 'OANDA',
  environment: 'PRACTICE',
  accountCurrency: 'USD',
  openTrades: [],
};

const activation = {
  activation: {
    activationId: '11111111-1111-1111-1111-111111111111',
  },
  replayed: false,
};

function renderActivation() {
  render(<PaperActivation />);
}

async function chooseVersionAndRisk() {
  const strategy = await screen.findByRole('combobox', { name: 'Strategy' });
  fireEvent.change(strategy, { target: { value: 'ema-sweep' } });
  const version = await screen.findByRole('combobox', {
    name: 'StrategyVersion',
  });
  fireEvent.change(version, { target: { value: 'ema-v2' } });
  const risk = screen.getByLabelText('Risk per trade (%)');
  fireEvent.change(risk, { target: { value: '0.5' } });
  return { strategy, version, risk };
}

async function prepareReview() {
  await chooseVersionAndRisk();
  fireEvent.click(screen.getByRole('button', { name: 'Review activation' }));
  await screen.findByText('Freeze the approval before submission');
  return screen.getByRole('button', { name: 'Activate PAPER trading' });
}

describe('PAPER activation workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('crypto', { randomUUID: vi.fn(() => 'review-request-id') });
    mocks.listStrategies.mockResolvedValue(catalog);
    mocks.getStrategy.mockResolvedValue(detail);
    mocks.paperCapability.mockResolvedValue(capability);
    mocks.activePaperStatus.mockResolvedValue(null);
    mocks.paperBrokerState.mockResolvedValue(broker);
    mocks.activatePaper.mockResolvedValue(activation);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('keeps Risk blank by default and loads StrategyVersion defaults', async () => {
    renderActivation();

    expect(
      await screen.findByRole('textbox', { name: 'Risk per trade (%)' }),
    ).toHaveValue('');
    await chooseVersionAndRisk();
    expect(screen.getByDisplayValue('2')).toBeInTheDocument();
    expect(screen.getByDisplayValue('close')).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: /v1.*unavailable/ }),
    ).toBeDisabled();
  });

  it('shows methodology and validates parameter values before review', async () => {
    renderActivation();
    await chooseVersionAndRisk();
    expect(
      screen.getByText('Sweep, confirm, and enter on completed bars.'),
    ).toBeInTheDocument();

    const bars = screen.getByLabelText('Confirmation bars');
    fireEvent.change(bars, { target: { value: '5' } });
    expect(screen.getByText('Must be at most 3.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Review activation' }),
    ).toBeDisabled();
  });

  it('rejects a missing or out-of-range Risk percentage', async () => {
    renderActivation();
    await chooseVersionAndRisk();
    const risk = screen.getByLabelText('Risk per trade (%)');
    fireEvent.change(risk, { target: { value: '100' } });
    expect(
      screen.getByText(/greater than 0% and less than 100%/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Review activation' }),
    ).toBeDisabled();
  });

  it('blocks unavailable capability, an active session, and visible broker exposure', async () => {
    mocks.paperCapability.mockResolvedValue({
      ...capability,
      available: false,
      reasonCode: 'OANDA_UNAVAILABLE',
    });
    renderActivation();
    await screen.findByText(/Unavailable\. Reason: OANDA_UNAVAILABLE/);
    await chooseVersionAndRisk();
    expect(
      screen.getByRole('button', { name: 'Review activation' }),
    ).toBeDisabled();
    cleanup();

    mocks.paperCapability.mockResolvedValue(capability);
    mocks.activePaperStatus.mockResolvedValue({
      activation: { activationId: 'existing' },
    });
    renderActivation();
    await screen.findByText(/An active PAPER session already exists/);
    await chooseVersionAndRisk();
    expect(
      screen.getByRole('button', { name: 'Review activation' }),
    ).toBeDisabled();
    cleanup();

    mocks.activePaperStatus.mockResolvedValue(null);
    mocks.paperBrokerState.mockResolvedValue({
      ...broker,
      openTrades: [{ tradeId: 'trade-1' }],
    });
    renderActivation();
    await screen.findByText(/1 visible open broker Trade found/);
    await chooseVersionAndRisk();
    expect(
      screen.getByRole('button', { name: 'Review activation' }),
    ).toBeDisabled();
  });

  it('discloses that an empty broker read is not proof of flatness', async () => {
    renderActivation();
    expect(
      await screen.findByText(/not proof of a flat account/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('secret-provider-account-id'),
    ).not.toBeInTheDocument();
  });

  it('blocks approval when broker state is unavailable', async () => {
    mocks.paperBrokerState.mockRejectedValue(new Error('broker read failed'));
    renderActivation();
    expect(
      await screen.findByText(/Open broker Trades are unknown/),
    ).toBeInTheDocument();
    await chooseVersionAndRisk();
    expect(
      screen.getByRole('button', { name: 'Review activation' }),
    ).toBeDisabled();
  });

  it('freezes the exact review and clears it when configuration changes', async () => {
    renderActivation();
    await prepareReview();
    expect(screen.getByText('PAPER')).toBeInTheDocument();
    expect(screen.getByText('OANDA Practice')).toBeInTheDocument();
    expect(screen.getByText(/0\.5% \(wire ratio 0\.005\)/)).toBeInTheDocument();
    expect(screen.getByText('review-request-id')).toBeInTheDocument();

    fireEvent.change(
      screen.getByRole('textbox', { name: 'Activation confirmation' }),
      {
        target: { value: 'ACTIVATE PAPER' },
      },
    );
    fireEvent.change(screen.getByLabelText('Confirmation bars'), {
      target: { value: '3' },
    });
    expect(
      screen.queryByRole('textbox', { name: 'Activation confirmation' }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Review activation' }),
    ).toBeInTheDocument();
  });

  it('generates a new review identity after an authority-bearing change', async () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi
        .fn()
        .mockReturnValueOnce('first-review-id')
        .mockReturnValueOnce('second-review-id'),
    });
    renderActivation();
    await prepareReview();
    expect(screen.getByText('first-review-id')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Risk per trade (%)'), {
      target: { value: '0.75' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Review activation' }));
    expect(screen.getByText('second-review-id')).toBeInTheDocument();
    expect(screen.queryByText('first-review-id')).not.toBeInTheDocument();
  });

  it('requires the exact typed phrase and submits one frozen request', async () => {
    renderActivation();
    const button = await prepareReview();
    expect(button).toBeDisabled();
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Activation confirmation' }),
      {
        target: { value: 'activate paper' },
      },
    );
    expect(button).toBeDisabled();
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Activation confirmation' }),
      {
        target: { value: 'ACTIVATE PAPER' },
      },
    );
    expect(button).toBeEnabled();

    let resolve: (value: typeof activation) => void = () => undefined;
    mocks.activatePaper.mockImplementation(
      () => new Promise<typeof activation>((complete) => (resolve = complete)),
    );
    fireEvent.click(button);
    fireEvent.click(button);
    expect(mocks.activatePaper).toHaveBeenCalledTimes(1);
    expect(mocks.activatePaper).toHaveBeenCalledWith({
      activationRequestId: 'review-request-id',
      strategyVersionId: 'ema-v2',
      parameters: { confirmation_bars: 2, entry_mode: 'close' },
      riskPerTrade: '0.005',
      confirmation: 'ACTIVATE_PAPER',
    });
    resolve(activation);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/paper'));
  });

  it('resolves an ambiguous POST by accepting a matching active read', async () => {
    renderActivation();
    mocks.activePaperStatus.mockResolvedValueOnce(null).mockResolvedValueOnce({
      activation: { activationId: 'review-request-id' },
    });
    mocks.activatePaper.mockRejectedValue(new Error('network timeout'));
    const button = await prepareReview();
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Activation confirmation' }),
      {
        target: { value: 'ACTIVATE PAPER' },
      },
    );
    fireEvent.click(button);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/paper'));
    expect(mocks.activatePaper).toHaveBeenCalledTimes(1);
    expect(mocks.activePaperStatus).toHaveBeenCalledTimes(2);
  });

  it('offers an explicit same-ID retry when ambiguous read finds no active session', async () => {
    renderActivation();
    mocks.activePaperStatus.mockResolvedValue(null);
    mocks.activatePaper
      .mockRejectedValueOnce(new Error('network timeout'))
      .mockResolvedValueOnce(activation);
    const button = await prepareReview();
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Activation confirmation' }),
      {
        target: { value: 'ACTIVATE PAPER' },
      },
    );
    fireEvent.click(button);
    const retry = await screen.findByRole('button', {
      name: 'Retry activation with same review',
    });
    expect(mocks.activatePaper).toHaveBeenCalledTimes(1);
    fireEvent.click(retry);
    await waitFor(() => expect(push).toHaveBeenCalledWith('/paper'));
    expect(mocks.activatePaper).toHaveBeenCalledTimes(2);
    expect(mocks.activatePaper.mock.calls[0][0].activationRequestId).toBe(
      mocks.activatePaper.mock.calls[1][0].activationRequestId,
    );
  });

  it('surfaces a different active activation as a conflict without retrying', async () => {
    renderActivation();
    mocks.activePaperStatus.mockResolvedValueOnce(null).mockResolvedValueOnce({
      activation: { activationId: 'different-request-id' },
    });
    mocks.activatePaper.mockRejectedValue(new Error('network timeout'));
    const button = await prepareReview();
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Activation confirmation' }),
      {
        target: { value: 'ACTIVATE PAPER' },
      },
    );
    fireEvent.click(button);
    expect(
      await screen.findByText(/different active PAPER session exists/),
    ).toBeInTheDocument();
    expect(mocks.activatePaper).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
  });
});
