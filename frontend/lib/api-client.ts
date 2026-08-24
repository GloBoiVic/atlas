import type { components, operations } from './api.generated';

const API_PREFIX = '/atlas-api';

export class ApiUnavailableError extends Error {
  constructor(message = 'Atlas API is unavailable.') {
    super(message);
    this.name = 'ApiUnavailableError';
  }
}

export class ApiTransportTimeoutError extends ApiUnavailableError {
  constructor() {
    super('The run command timed out before Atlas confirmed its outcome.');
    this.name = 'ApiTransportTimeoutError';
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs?: number,
): Promise<T> {
  const controller = timeoutMs ? new AbortController() : undefined;
  const timeout = timeoutMs
    ? globalThis.setTimeout(() => controller?.abort(), timeoutMs)
    : undefined;
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      ...init,
      signal: controller?.signal ?? init?.signal,
      headers: { Accept: 'application/json', ...init?.headers },
    });
  } catch {
    if (controller?.signal.aborted) throw new ApiTransportTimeoutError();
    throw new ApiUnavailableError();
  } finally {
    if (timeout) globalThis.clearTimeout(timeout);
  }

  if (!response.ok) {
    throw new ApiUnavailableError(`Atlas API returned ${response.status}.`);
  }

  return (await response.json()) as T;
}

export const atlasApi = {
  ready: () =>
    request<
      operations['ready_health_ready_get']['responses'][200]['content']['application/json']
    >('/health/ready'),
  listExperiments: (
    query?: operations['listing_api_v1_experiments_get']['parameters']['query'],
  ) => {
    const params = new URLSearchParams();
    if (query?.limit !== undefined) params.set('limit', String(query.limit));
    if (query?.cursor) params.set('cursor', query.cursor);
    const suffix = params.size ? `?${params.toString()}` : '';
    return request<unknown>(`/api/v1/experiments${suffix}`);
  },
  listStrategies: () =>
    request<components['schemas']['StrategyCatalogResponse']>(
      '/api/v1/strategies',
    ),
  getStrategy: (strategyKey: string) =>
    request<components['schemas']['StrategyDetailResponse']>(
      `/api/v1/strategies/${encodeURIComponent(strategyKey)}`,
    ),
  compareExperiments: (experimentIds: string[]) => {
    const params = new URLSearchParams();
    experimentIds.forEach((id) => params.append('experimentId', id));
    return request<components['schemas']['ExperimentComparisonResponse']>(
      `/api/v1/experiments/comparison?${params.toString()}`,
    );
  },
  configurationOptions: () =>
    request<unknown>('/api/v1/experiments/configuration-options'),
  validateCoverage: (body: components['schemas']['PeriodRequest']) =>
    request<unknown>('/api/v1/experiments/coverage-validations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  createExperiment: (body: components['schemas']['ExperimentCreateRequest']) =>
    request<unknown>('/api/v1/experiments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  getExperiment: (id: string) => request<unknown>(`/api/v1/experiments/${id}`),
  runExperiment: (id: string) =>
    request<unknown>(`/api/v1/experiments/${id}/run`, { method: 'POST' }, 8000),
  getEquity: (id: string) =>
    request<unknown>(`/api/v1/experiments/${id}/equity`),
  listTrades: (id: string, afterSequence = 0) =>
    request<unknown>(
      `/api/v1/experiments/${id}/trades?limit=250&afterSequence=${afterSequence}`,
    ),
  getTrade: (id: string, sequence: number) =>
    request<unknown>(`/api/v1/experiments/${id}/trades/${sequence}`),
};
