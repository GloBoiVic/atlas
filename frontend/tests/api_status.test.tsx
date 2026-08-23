import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiStatus } from '../components/api-status';

describe('API status', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  });

  it('keeps an unavailable API state visible', async () => {
    render(<ApiStatus />);
    expect(await screen.findByRole('status')).toHaveTextContent(
      'API unavailable',
    );
    expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible();
  });

  it('shows the connected state when the ready path responds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'ok' }),
      }),
    );

    render(<ApiStatus />);

    expect(await screen.findByText('PAPER · connected')).toBeVisible();
    expect(fetch).toHaveBeenCalledWith(
      '/atlas-api/health/ready',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    );
  });
});
