import { render, screen } from '@testing-library/react';
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

    expect(table).toHaveTextContent('0.125');
    expect(rows[1]).toHaveTextContent('0.125');
    expect(rows[2]).toHaveTextContent('—');
  });
});
