import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const setTimeZone = vi.fn();

vi.mock('next/navigation', () => ({ usePathname: () => '/strategies' }));
vi.mock('../components/api-status', () => ({
  ApiStatus: () => <span>API ready</span>,
}));
vi.mock('../app/providers', () => ({
  useDisplayTimeZone: () => ({
    timeZone: 'America/Chicago',
    setTimeZone,
  }),
}));

import { AppShell } from '../components/app-shell';

describe('trader shell', () => {
  it('keeps navigation, status, and timezone context without diagnostic strips', () => {
    render(
      <AppShell>
        <p>Workspace content</p>
      </AppShell>,
    );

    expect(screen.queryByText('Historical research')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Strategies are authored and versioned'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('Experiments are deterministic historical research'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('PAPER status is observable, not controllable here'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('LIVE is a future capability'),
    ).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Atlas' })).toHaveAttribute(
      'href',
      '/',
    );
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'href',
      '/',
    );
    expect(screen.getByRole('link', { name: 'PAPER' })).toHaveAttribute(
      'href',
      '/paper',
    );
    expect(screen.getByRole('link', { name: 'Data' })).toHaveAttribute(
      'href',
      '/data',
    );
    expect(screen.getByRole('link', { name: 'Experiments' })).toHaveAttribute(
      'href',
      '/experiments',
    );
    expect(screen.getByRole('link', { name: 'Strategies' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: 'Overview' })).not.toHaveAttribute(
      'aria-current',
    );
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument();
    expect(screen.queryByText('Deployments')).not.toBeInTheDocument();
    expect(screen.queryByText('Journal')).not.toBeInTheDocument();
    expect(screen.getByText('LIVE').closest('a')).toBeNull();
    expect(screen.getByRole('link', { name: 'Strategies' })).toHaveAttribute(
      'href',
      '/strategies',
    );
    const navigation = screen.getByRole('navigation', { name: 'Primary' });
    expect(navigation).toHaveClass(
      'min-w-0',
      'flex-1',
      'basis-full',
      'order-3',
      'contain-paint',
      'overflow-x-auto',
    );
    expect(screen.getByRole('link', { name: 'Strategies' })).toHaveClass(
      'shrink-0',
      'whitespace-nowrap',
    );
    expect(
      screen.getByRole('combobox', { name: 'Display timezone' }),
    ).toHaveValue('America/Chicago');
    expect(screen.queryByText(/Times shown in/)).not.toBeInTheDocument();
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Display timezone' }),
      {
        target: { value: 'UTC' },
      },
    );
    expect(setTimeZone).toHaveBeenCalledWith('UTC');
    expect(screen.getByRole('link', { name: 'Atlas' })).toHaveClass(
      'focus-visible:ring-2',
    );
  });
});
