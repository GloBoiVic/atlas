import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('next/navigation', () => ({ usePathname: () => '/strategies' }));
vi.mock('../components/api-status', () => ({
  ApiStatus: () => <span>PAPER · connected</span>,
}));
vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({
    timeZone: 'America/Chicago',
    setTimeZone: vi.fn(),
  }),
}));

import { AppShell } from '../components/app-shell';

describe('historical research workstation shell', () => {
  it('makes the current capability and future-only navigation explicit', () => {
    render(
      <AppShell>
        <p>Workspace content</p>
      </AppShell>,
    );

    expect(screen.getByText('Historical research')).toBeInTheDocument();
    expect(
      screen.getByText('Experiments are available now'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('PAPER and LIVE are future-only'),
    ).toBeInTheDocument();
    expect(screen.getByText('Dashboard').closest('a')).toBeNull();
    expect(screen.getByText('Deployments').closest('a')).toBeNull();
    expect(screen.getByRole('link', { name: 'Strategies' })).toHaveAttribute(
      'href',
      '/strategies',
    );
  });
});
