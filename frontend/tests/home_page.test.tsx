import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Home from '../app/page';

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

vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({ timeZone: 'UTC', setTimeZone: vi.fn() }),
}));

vi.mock('../lib/api-client', () => ({
  atlasApi: {
    ready: vi
      .fn()
      .mockResolvedValue({ status: 'ready', checks: { database: 'ok' } }),
    listStrategies: vi.fn().mockResolvedValue({ items: [] }),
    listExperiments: vi.fn().mockResolvedValue({ items: [] }),
    paperCapability: vi.fn().mockResolvedValue({
      provider: 'OANDA Practice',
      environment: 'practice',
      instrument: 'EUR/USD',
      available: true,
      reasonCode: null,
    }),
    activePaperStatus: vi.fn().mockResolvedValue(null),
    historicalCapability: vi.fn().mockResolvedValue({
      provider: 'OANDA Practice',
      instrument: 'EUR/USD',
      products: [],
      available: true,
      reasonCode: null,
    }),
    configurationOptions: vi.fn().mockResolvedValue({
      strategyVersions: [],
      datasetSnapshots: [],
      defaults: {},
      simulationAssumptions: {},
    }),
  },
}));

vi.mock('../components/app-shell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('home page', () => {
  it('renders the Overview route instead of redirecting', () => {
    render(<Home />);

    expect(
      screen.getByRole('heading', { name: 'Overview' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/creates methodologies/)).toBeInTheDocument();
  });
});
