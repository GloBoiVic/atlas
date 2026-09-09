import { afterEach, describe, expect, it, vi } from 'vitest';
import { atlasApi } from '../lib/api-client';

describe('comparison API client contract', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('sends two through four ordered experimentId query values', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    for (const ids of [
      ['one', 'two'],
      ['one', 'two', 'three'],
      ['one', 'two', 'three', 'four'],
    ]) {
      await atlasApi.compareExperiments(ids);
      const requestUrl = new URL(
        fetchMock.mock.lastCall?.[0] as string,
        'http://localhost',
      );
      expect(requestUrl.searchParams.getAll('experimentId')).toEqual(ids);
      expect(requestUrl.searchParams.getAll('experiment_id')).toEqual([]);
    }
  });

  it('uses typed safe PAPER and historical-data GET paths', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await atlasApi.paperCapability();
    await atlasApi.paperBrokerState();
    await atlasApi.activePaperStatus();
    await atlasApi.historicalCapability();
    await atlasApi.activeHistoricalLoad();

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/atlas-api/api/v1/paper/capability',
      '/atlas-api/api/v1/paper/broker-state',
      '/atlas-api/api/v1/paper/activations/active',
      '/atlas-api/api/v1/historical-data/capability',
      '/atlas-api/api/v1/historical-data/load-requests/active',
    ]);
    expect(
      fetchMock.mock.calls.every(([, init]) => init?.method === undefined),
    ).toBe(true);
  });

  it('does not map paper broker 404 to empty', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({
          error: { code: 'SOME_NOT_FOUND', message: 'not found' },
        }),
      }),
    );
    await expect(atlasApi.paperBrokerState()).rejects.toMatchObject({
      code: 'SOME_NOT_FOUND',
    });
  });

  it('represents missing active PAPER and historical loads as null', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({
        error: {
          code: 'PAPER_ACTIVATION_NOT_ACTIVE',
          message: 'No PAPER activation is active.',
        },
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(atlasApi.activePaperStatus()).resolves.toBeNull();

    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        error: {
          code: 'HISTORICAL_LOAD_NOT_ACTIVE',
          message: 'No historical load is active.',
        },
      }),
    });
    await expect(atlasApi.activeHistoricalLoad()).resolves.toBeNull();
  });

  it('does not hide unrelated active-state errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({
          error: {
            code: 'PAPER_RUNTIME_INTERNAL_ERROR',
            message: 'Unavailable',
          },
        }),
      }),
    );

    await expect(atlasApi.activePaperStatus()).rejects.toMatchObject({
      code: 'PAPER_RUNTIME_INTERNAL_ERROR',
      status: 503,
    });
  });
});
