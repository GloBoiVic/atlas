import type { components, operations } from './api.generated';

const API_PREFIX = '/atlas-api';

export type ExperimentPayload = Record<string, unknown> & {
  id?: string;
  status?: string;
};
export type TradeDetailPayload = Record<string, unknown> & {
  summary?: Record<string, unknown>;
  chart?: Record<string, unknown>;
  landmarks?: Record<string, unknown>[];
  evidence?: Record<string, unknown>[];
};

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
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown = {},
  ) {
    super(message);
    this.name = 'ApiError';
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
    let body: unknown = {};
    try {
      body = await response.json();
    } catch {
      /* stable fallback below */
    }
    const maybeError =
      typeof body === 'object' && body !== null && 'error' in body
        ? (
            body as {
              error?: {
                code?: unknown;
                message?: unknown;
                details?: unknown;
              };
            }
          ).error
        : undefined;
    // FastAPI Pydantic validation returns {detail: [{loc, msg, type}]} — surface it as HTTP_422 with structured fields
    const validation =
      typeof body === 'object' && body !== null && 'detail' in body
        ? (body as { detail?: unknown }).detail
        : undefined;
    if (Array.isArray(validation)) {
      const fields = Object.fromEntries(
        validation.map((item: unknown) => {
          const v =
            typeof item === 'object' && item !== null
              ? (item as { loc?: unknown; msg?: unknown })
              : {};
          const loc = Array.isArray(v.loc)
            ? v.loc.join('.')
            : String(v.loc ?? 'field');
          return [loc, String(v.msg ?? 'Invalid value')];
        }),
      );
      throw new ApiError(
        response.status,
        `HTTP_${response.status}`,
        `Validation failed — ${validation.map((i: unknown) => String((i as { msg?: string }).msg ?? '')).join('; ') || `Atlas API returned ${response.status}.`}`,
        { fields },
      );
    }
    throw new ApiError(
      response.status,
      typeof maybeError?.code === 'string'
        ? maybeError.code
        : `HTTP_${response.status}`,
      typeof maybeError?.message === 'string'
        ? maybeError.message
        : `Atlas API returned ${response.status}.`,
      maybeError?.details ?? {},
    );
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
    request<components['schemas']['ExperimentConfigurationOptionsResponse']>(
      '/api/v1/experiments/configuration-options',
    ),
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
  getExperiment: (id: string) =>
    request<ExperimentPayload>(`/api/v1/experiments/${id}`),
  deleteExperiment: (
    id: string,
    body: components['schemas']['ExperimentDeleteRequest'],
  ) =>
    request<components['schemas']['ExperimentDeleteResponse']>(
      `/api/v1/experiments/${id}`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    ),
  runExperiment: (id: string) =>
    request<unknown>(`/api/v1/experiments/${id}/run`, { method: 'POST' }, 8000),
  getEquity: (id: string) =>
    request<unknown>(`/api/v1/experiments/${id}/equity`),
  getPriceAnalysis: (id: string) =>
    request<components['schemas']['PriceAnalysisResponse']>(
      `/api/v1/experiments/${id}/price-analysis`,
    ),
  listTrades: (id: string, afterSequence = 0) =>
    request<unknown>(
      `/api/v1/experiments/${id}/trades?limit=250&afterSequence=${afterSequence}`,
    ),
  getTrade: (id: string, sequence: number) =>
    request<TradeDetailPayload>(`/api/v1/experiments/${id}/trades/${sequence}`),
  historicalCapability: () =>
    request<unknown>('/api/v1/historical-data/capability'),
  activeHistoricalLoad: () =>
    request<unknown>('/api/v1/historical-data/load-requests/active').catch(
      (error) => {
        // An absent active request is the expected empty state on first load.
        if (
          error instanceof ApiError &&
          error.code === 'HISTORICAL_LOAD_NOT_ACTIVE'
        )
          return null;
        throw error;
      },
    ),
  createHistoricalLoad: (
    body: components['schemas']['HistoricalDataLoadRequest'],
  ) =>
    request<unknown>('/api/v1/historical-data/load-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  historicalLoadStatus: (id: string) =>
    request<unknown>(
      `/api/v1/historical-data/load-requests/${encodeURIComponent(id)}`,
    ),
};
