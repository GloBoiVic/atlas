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
});
