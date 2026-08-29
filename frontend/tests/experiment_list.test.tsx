import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
vi.mock('../lib/api-client', () => ({
  atlasApi: {
    listExperiments: vi.fn(),
  },
  ApiTransportTimeoutError: class ApiTransportTimeoutError extends Error {},
}));

import { ExperimentsList } from '../components/experiment-workflow';
import { atlasApi } from '../lib/api-client';

describe('Experiment list metric cells', () => {
  beforeEach(() => {
    vi.mocked(atlasApi.listExperiments).mockResolvedValue({
      items: [
        {
          id: 'experiment-value',
          status: 'COMPLETED',
          strategyVersionId: 'strategy-value',
          tradingStart: '2024-01-01T00:00:00Z',
          tradingEnd: '2024-01-02T00:00:00Z',
          createdAt: '2024-01-03T00:00:00Z',
          metrics: {
            maxDrawdownPercent: {
              state: 'VALUE',
              value: '0.125',
              unit: 'RATIO',
              reason: null,
            },
          },
        },
        {
          id: 'experiment-unavailable',
          status: 'COMPLETED',
          strategyVersionId: 'strategy-value',
          tradingStart: '2024-01-01T00:00:00Z',
          tradingEnd: '2024-01-02T00:00:00Z',
          createdAt: '2024-01-04T00:00:00Z',
          metrics: {
            maxDrawdownPercent: {
              state: 'UNAVAILABLE',
              value: null,
              unit: 'RATIO',
              reason: 'ZERO_TRADES',
            },
          },
        },
      ],
    });
  });

  it('renders canonical max drawdown percent values and preserves unavailable state', async () => {
    render(<ExperimentsList />);

    const table = await screen.findByRole('table');
    const rows = screen.getAllByRole('row');

    expect(table).toHaveTextContent('12.50%');
    expect(rows[1]).toHaveTextContent('12.50%');
    expect(rows[2]).toHaveTextContent('—');
  });

  it('uses the authoritative label and period, then follows the next cursor', async () => {
    vi.mocked(atlasApi.listExperiments)
      .mockResolvedValueOnce({
        items: [
          {
            id: 'first-id',
            label: 'EUR/USD sweep · January sample',
            status: 'PENDING',
            strategy: { displayName: 'EMA Sweep Confirmation Break v2' },
            tradingStart: '2024-01-01T00:00:00Z',
            tradingEnd: '2024-01-02T00:00:00Z',
            createdAt: '2024-01-03T00:00:00Z',
          },
        ],
        nextCursor: 'cursor-2',
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'second-id',
            label: 'EUR/USD sweep · February sample',
            status: 'FAILED',
            tradingStart: '2024-02-01T00:00:00Z',
            tradingEnd: '2024-02-02T00:00:00Z',
            createdAt: '2024-02-03T00:00:00Z',
          },
        ],
        nextCursor: null,
      });

    render(<ExperimentsList />);

    expect(
      await screen.findByText('EUR/USD sweep · January sample'),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'Load more Experiments' }),
    );

    expect(
      await screen.findByText('EUR/USD sweep · February sample'),
    ).toBeInTheDocument();
    expect(atlasApi.listExperiments).toHaveBeenLastCalledWith({
      limit: 50,
      cursor: 'cursor-2',
    });
  });
});
