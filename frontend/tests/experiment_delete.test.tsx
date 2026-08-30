import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  route: { experimentId: 'experiment-1' },
}));

vi.mock('../components/experiments/experiment-results', () => ({
  ExperimentResults: () => null,
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
  usePathname: () => '/experiments/experiment-1',
  useRouter: () => ({ push: mocks.push }),
}));

import { ExperimentStatusPage } from '../components/experiment-workflow';
import {
  ApiError,
  ApiTransportTimeoutError,
  ApiUnavailableError,
  atlasApi,
} from '../lib/api-client';

const pending = () => ({
  id: 'experiment-1',
  label: 'Experiment · 2026-01-05 → 2026-01-31',
  status: 'PENDING',
  strategy: { displayName: 'EMA Sweep Confirmation Break v2' },
  createdAt: '2026-01-04T00:00:00Z',
  tradingStart: '2026-01-05T00:00:00Z',
  tradingEnd: '2026-01-31T00:00:00Z',
  startingCapital: '10000',
  riskPerTrade: '0.01',
  identity: {
    instrument: { code: 'EUR/USD' },
    provider: { name: 'OANDA' },
    analytical: { resolution: 'M15', priceComponent: 'MID' },
    tradingPeriod: {
      start: '2026-01-05T00:00:00Z',
      end: '2026-01-31T00:00:00Z',
    },
  },
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(atlasApi, 'ready').mockResolvedValue({
    status: 'ready',
    service: 'atlas-api',
    checks: {},
  });
  vi.spyOn(atlasApi, 'getExperiment').mockResolvedValue(pending());
  vi.spyOn(atlasApi, 'deleteExperiment').mockResolvedValue({
    deleted: true,
    experimentId: 'experiment-1',
    snapshot: { id: 'snapshot-1', deleted: true },
  });
});

afterEach(() => cleanup());

describe('Experiment deletion workflow', () => {
  it('uses modal semantics, makes the page inert, traps focus, and supports cancel', async () => {
    render(<ExperimentStatusPage />);
    const trigger = await screen.findByRole('button', {
      name: 'Delete Experiment',
    });
    fireEvent.click(trigger);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(
      document.querySelector('[data-delete-page-content]'),
    ).toHaveAttribute('inert');
    expect(screen.getByLabelText(/Type DELETE/)).toHaveAttribute(
      'name',
      'delete-confirmation',
    );
    const confirmation = screen.getByLabelText(/Type DELETE/);
    const cancel = screen.getByRole('button', { name: 'Cancel' });
    expect(confirmation).toHaveFocus();

    cancel.focus();
    fireEvent.keyDown(cancel, { key: 'Tab' });
    expect(confirmation).toHaveFocus();
    fireEvent.keyDown(confirmation, { key: 'Tab', shiftKey: true });
    expect(cancel).toHaveFocus();

    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();

    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('requires exact DELETE, sends human facts, and navigates after one success', async () => {
    render(<ExperimentStatusPage />);
    fireEvent.click(
      await screen.findByRole('button', { name: 'Delete Experiment' }),
    );

    expect(screen.getByRole('dialog')).toHaveTextContent(
      'Shared DatasetSnapshot data, canonical bars, and acquisition history are retained.',
    );
    const submit = screen.getByRole('button', { name: 'Delete permanently' });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Type DELETE/), {
      target: { value: 'DELETE' },
    });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() =>
      expect(atlasApi.deleteExperiment).toHaveBeenCalledTimes(1),
    );
    expect(atlasApi.deleteExperiment).toHaveBeenCalledWith('experiment-1', {
      confirmation: 'DELETE',
      expected: {
        label: 'Experiment · 2026-01-05 → 2026-01-31',
        status: 'PENDING',
        strategy: 'EMA Sweep Confirmation Break v2',
        instrument: 'EUR/USD',
        provider: 'OANDA',
        analysis: 'native M15 MID',
        tradingPeriod: {
          start: '2026-01-05T00:00:00Z',
          end: '2026-01-31T00:00:00Z',
        },
      },
    });
    expect(mocks.push).toHaveBeenCalledWith('/experiments');
  });

  it('prevents double submit and keeps the dialog open for unknown outcomes', async () => {
    let rejectDelete!: (reason?: unknown) => void;
    vi.mocked(atlasApi.deleteExperiment).mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectDelete = reject;
      }),
    );
    render(<ExperimentStatusPage />);
    fireEvent.click(
      await screen.findByRole('button', { name: 'Delete Experiment' }),
    );
    fireEvent.change(screen.getByLabelText(/Type DELETE/), {
      target: { value: 'DELETE' },
    });
    const submit = screen.getByRole('button', { name: 'Delete permanently' });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(atlasApi.deleteExperiment).toHaveBeenCalledTimes(1);
    expect(submit).toBeDisabled();
    rejectDelete(
      new ApiError(500, 'EXPERIMENT_DELETE_FAILED', 'Deletion failed.'),
    );
    expect(await screen.findByText('Deletion failed.')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(mocks.push).not.toHaveBeenCalled();
  });

  it.each([
    [
      'EXPERIMENT_DELETE_FAILED',
      new ApiError(
        500,
        'EXPERIMENT_DELETE_FAILED',
        'Experiment deletion failed and was rolled back.',
      ),
      'Experiment deletion failed and was rolled back.',
    ],
    [
      'LOCAL_PEER_REQUIRED',
      new ApiError(
        403,
        'LOCAL_PEER_REQUIRED',
        'Atlas API is available only from the local machine.',
      ),
      'Atlas API is available only from the local machine.',
    ],
    [
      'unavailable',
      new ApiUnavailableError('Atlas API is unavailable.'),
      'Atlas API is unavailable.',
    ],
    [
      'transport timeout',
      new ApiTransportTimeoutError(),
      'The run command timed out before Atlas confirmed its outcome.',
    ],
  ])(
    'renders %s deletion failures inside the active dialog',
    async (_label, reason, message) => {
      vi.mocked(atlasApi.deleteExperiment).mockRejectedValue(reason);
      render(<ExperimentStatusPage />);
      fireEvent.click(
        await screen.findByRole('button', { name: 'Delete Experiment' }),
      );
      const confirmation = screen.getByLabelText(/Type DELETE/);
      fireEvent.change(confirmation, { target: { value: 'DELETE' } });
      fireEvent.click(
        screen.getByRole('button', { name: 'Delete permanently' }),
      );

      const dialog = await screen.findByRole('dialog');
      const error = await within(dialog).findByRole('status');
      expect(error).toBeVisible();
      expect(error).toHaveTextContent(message);
      if (reason instanceof ApiError) {
        expect(error).toHaveTextContent(`Code: ${reason.code}`);
      }
      expect(confirmation).toHaveValue('DELETE');
      expect(
        screen.queryByRole('button', { name: 'Retry' }),
      ).not.toBeInTheDocument();
      expect(atlasApi.deleteExperiment).toHaveBeenCalledTimes(1);
      expect(mocks.push).not.toHaveBeenCalled();
    },
  );

  it('hides deletion for RUNNING Experiments with a persistent explanation', async () => {
    vi.mocked(atlasApi.getExperiment).mockResolvedValue({
      ...pending(),
      status: 'RUNNING',
    });
    render(<ExperimentStatusPage />);
    expect(
      await screen.findByText('Running Experiments cannot be deleted.'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Delete Experiment' }),
    ).not.toBeInTheDocument();
  });

  it('refetches after a locked status conflict and requires fresh confirmation', async () => {
    vi.mocked(atlasApi.deleteExperiment).mockRejectedValue(
      new ApiError(
        409,
        'DELETE_CONFIRMATION_MISMATCH',
        'The Experiment facts changed; review and confirm again.',
      ),
    );
    render(<ExperimentStatusPage />);
    fireEvent.click(
      await screen.findByRole('button', { name: 'Delete Experiment' }),
    );
    fireEvent.change(screen.getByLabelText(/Type DELETE/), {
      target: { value: 'DELETE' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    expect(
      await screen.findByText(
        'The Experiment facts changed; review and confirm again.',
      ),
    ).toBeInTheDocument();
    expect(atlasApi.getExperiment).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
