import { afterEach, describe, expect, it, vi } from 'vitest';

describe('Next API rewrite', () => {
  afterEach(() => {
    delete process.env.ATLAS_API_BASE_URL;
    vi.resetModules();
  });

  it('maps the same-origin prefix directly onto the configured API base', async () => {
    process.env.ATLAS_API_BASE_URL = 'http://localhost:8000/';
    const { default: config } = await import('../next.config');
    const rewrites = await config.rewrites?.();

    expect(Array.isArray(rewrites)).toBe(true);
    expect(rewrites).toEqual([
      {
        source: '/atlas-api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ]);
    if (!Array.isArray(rewrites)) throw new Error('Expected rewrite array');
    expect(rewrites[0]?.destination).not.toContain('/api/:path*');
  });
});
