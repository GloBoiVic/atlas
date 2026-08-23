import { describe, expect, it, vi } from 'vitest';
import { redirect } from 'next/navigation';
import Home from '../app/page';

vi.mock('next/navigation', () => ({ redirect: vi.fn() }));

describe('home page', () => {
  it('redirects to the Experiments workspace', () => {
    vi.mocked(redirect).mockClear();
    Home();
    expect(redirect).toHaveBeenCalledWith('/experiments');
  });
});
