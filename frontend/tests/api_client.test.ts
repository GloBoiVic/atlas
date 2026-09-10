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

  it('requests bounded completed PAPER trade history with the typed response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(atlasApi.listPaperTrades({ limit: 20 })).resolves.toEqual({
      items: [],
    });

    const requestUrl = new URL(
      fetchMock.mock.lastCall?.[0] as string,
      'http://localhost',
    );
    expect(requestUrl.pathname).toBe('/atlas-api/api/v1/paper/trades');
    expect(requestUrl.searchParams.get('limit')).toBe('20');
    expect(fetchMock.mock.lastCall?.[1]?.method).toBeUndefined();
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

  it('posts the stable typed PAPER activation body without changing its risk string', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ activation: {}, replayed: false }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const body = {
      activationRequestId: '11111111-1111-1111-1111-111111111111',
      strategyVersionId: '22222222-2222-2222-2222-222222222222',
      parameters: { lookback: 20 },
      riskPerTrade: '0.005',
      confirmation: 'ACTIVATE_PAPER' as const,
    };

    await atlasApi.activatePaper(body);

    expect(fetchMock).toHaveBeenCalledWith(
      '/atlas-api/api/v1/paper/activations',
      expect.objectContaining({
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }),
    );
  });

  it('gets PAPER activation detail by its encoded ID', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ activation: {} }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await atlasApi.paperStatus('activation/request');

    expect(fetchMock).toHaveBeenCalledWith(
      '/atlas-api/api/v1/paper/activations/activation%2Frequest',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    );
  });

  it('posts the bounded runtime-only PAPER stop request', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ activationId: 'activation-1' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const body = { reason: 'Trader requested stop from Atlas UI.' };

    await atlasApi.stopPaper('activation-1', body);

    expect(fetchMock).toHaveBeenCalledWith(
      '/atlas-api/api/v1/paper/activations/activation-1/stop',
      expect.objectContaining({
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }),
    );
  });
});
