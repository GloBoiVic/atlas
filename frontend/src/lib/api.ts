import axios from "axios";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

export type BacktestStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface BacktestResult {
  total_return: string;
  total_pnl: string;
  starting_equity: string;
  ending_equity: string;
  max_drawdown: string | null;
  win_rate: number | null;
  sharpe_ratio: number | null;
  profit_factor: number | null;
  trade_count: number;
  winning_trade_count: number;
  losing_trade_count: number;
}

export interface BacktestRun {
  id: string;
  strategy_name: string;
  strategy_version: string;
  strategy_commit_sha: string;
  strategy_parameters: Record<string, unknown>;
  instrument_id: string;
  symbol: string;
  timeframe: string;
  data_source: string;
  dataset_id: string;
  start_date: string;
  end_date: string;
  risk_config: Record<string, unknown>;
  execution_config: Record<string, unknown>;
  fill_model: string;
  status: BacktestStatus;
  created_at: string;
  result: BacktestResult | null;
  error_message: string | null;
  last_processed_timestamp: string | null;
  completed_at: string | null;
}

export interface BacktestTrade {
  id: string;
  backtest_run_id: string;
  instrument_id: string;
  symbol: string;
  direction: string;
  entry_price: string;
  exit_price: string | null;
  quantity: string;
  pnl: string | null;
  entry_time: string;
  exit_time: string | null;
  signal_metadata: Record<string, unknown>;
}

export interface BacktestCreateRequest {
  instrument_id: string;
  account_id: string;
  strategy_version_id: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  strategy_parameters: Record<string, unknown>;
  risk_config: Record<string, unknown>;
  execution_config: Record<string, unknown>;
  initial_balance: string;
}

export async function listBacktests(): Promise<BacktestRun[]> {
  const response = await api.get<BacktestRun[]>('/backtests');
  return response.data;
}

export async function getBacktest(id: string): Promise<BacktestRun> {
  const response = await api.get<BacktestRun>(`/backtests/${id}`);
  return response.data;
}

export async function getBacktestTrades(id: string): Promise<BacktestTrade[]> {
  const response = await api.get<BacktestTrade[]>(`/backtests/${id}/trades`);
  return response.data;
}

export async function createBacktest(
  request: BacktestCreateRequest,
): Promise<BacktestRun> {
  const response = await api.post<BacktestRun>('/backtests', request);
  return response.data;
}

export interface JournalEntry {
  id: string;
  account_id: string;
  trade_id: string;
  bot_id: string | null;
  strategy_version_id: string | null;
  instrument_id: string | null;
  symbol: string;
  direction: "long" | "short" | string;
  entry_price: string;
  exit_price: string | null;
  quantity: string;
  pnl: string | null;
  strategy_name: string;
  signal: Record<string, unknown>;
  market_conditions: Record<string, unknown>;
  notes: string | null;
  risk_metadata: Record<string, unknown>;
  opened_at: string;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JournalListFilters {
  start_date?: string;
  end_date?: string;
  bot_id?: string;
}

export interface JournalNotesUpdateRequest {
  notes: string | null;
}

export async function listJournalEntries(
  filters: JournalListFilters = {},
): Promise<JournalEntry[]> {
  const response = await api.get<JournalEntry[]>('/journal', { params: filters });
  return response.data;
}

export async function updateJournalNotes(
  id: string,
  request: JournalNotesUpdateRequest,
): Promise<JournalEntry> {
  const response = await api.patch<JournalEntry>(`/journal/${id}/notes`, request);
  return response.data;
}

export interface EquityPoint {
  timestamp: string;
  equity: string;
  net_pnl: string;
  trade_id: string | null;
}

export interface AnalyticsResponse {
  total_return: string;
  total_pnl: string;
  starting_equity: string;
  ending_equity: string;
  win_rate: number;
  closed_trade_daily_sharpe: number | null;
  max_drawdown: string;
  profit_factor: number | null;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  equity_curve: EquityPoint[];
}

export interface AnalyticsFilters {
  start_date?: string;
  end_date?: string;
}

export async function getAnalytics(
  filters: AnalyticsFilters = {},
): Promise<AnalyticsResponse> {
  const response = await api.get<AnalyticsResponse>('/analytics', { params: filters });
  return response.data;
}

export interface AccountSummary {
  account: {
    id: string;
    name: string;
    broker: string;
    mode: string;
    updated_at: string;
  };
  starting_equity: string;
  realized_pnl: string;
  unrealized_pnl: string;
  equity: string;
  as_of: string;
}

export interface Position {
  id: string;
  account_id: string;
  bot_id: string | null;
  strategy_version_id: string | null;
  instrument_id: string;
  symbol: string;
  mode: string;
  side: string;
  quantity: string;
  entry_price: string;
  current_price: string | null;
  unrealized_pnl: string;
  realized_pnl: string;
  opened_at: string;
}

export interface Bot {
  id: string;
  account_id: string;
  strategy_id: string | null;
  strategy_version_id: string | null;
  name: string;
  broker: string;
  /** Wire values remain open so an unexpected backend mode cannot become a UI control. */
  mode: string;
  instrument: string;
  timeframe: string;
  desired_status: string;
  status: string;
  pnl: string | null;
  config?: Record<string, unknown>;
  last_error: string | null;
  started_at: string | null;
  stopped_at: string | null;
  updated_at: string;
}

export type BotMode = "paper" | "testnet";

export function isSupportedBotMode(value: string): value is BotMode {
  return value === "paper" || value === "testnet";
}

export interface Trade {
  id: string;
  account_id: string;
  bot_id: string | null;
  strategy_version_id: string | null;
  instrument_id: string;
  symbol: string;
  mode: string;
  direction: string;
  entry_price: string;
  exit_price: string | null;
  quantity: string;
  gross_pnl: string | null;
  net_pnl: string | null;
  total_fees: string;
  status: string;
  entry_time: string;
  exit_time: string | null;
}

export interface Strategy {
  id: string;
  name: string;
  version: string;
  commit_sha: string;
  parameters: Record<string, unknown>;
  description: string | null;
  created_at: string;
  versions: Array<{
    id: string;
    strategy_id: string;
    repository: string;
    commit_sha: string;
    parameters: Record<string, unknown>;
    deployed_at: string;
  }>;
}

export interface DashboardSummary {
  account: AccountSummary;
  positions: Position[];
  bots: Bot[];
  recent_trades: Trade[];
}

export interface HealthResponse {
  status: string;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const response = await api.get<DashboardSummary>("/dashboard", { params: { limit: 10 } });
  return response.data;
}

export async function getAccountSummary(): Promise<AccountSummary> {
  const response = await api.get<AccountSummary>("/account");
  return response.data;
}

export async function listPositions(): Promise<Position[]> {
  const response = await api.get<Position[]>("/positions");
  return response.data;
}

export async function listBots(): Promise<Bot[]> {
  const response = await api.get<Bot[]>("/bots");
  return response.data;
}

export interface BotCreateRequest {
  name: string;
  strategy_version_id: string;
  account_id: string;
  broker: string;
  mode: BotMode;
  instrument: string;
  timeframe: string;
  config: Record<string, unknown>;
}

export interface BotUpdateRequest {
  name?: string;
  strategy_version_id?: string;
  broker?: string;
  mode?: BotMode;
  instrument?: string;
  timeframe?: string;
  config?: Record<string, unknown>;
}

export async function listScopedBots(
  accountId: string,
  mode: BotMode,
): Promise<Bot[]> {
  const response = await api.get<Bot[]>("/bots", {
    params: { account_id: accountId, mode },
  });
  return response.data;
}

export async function createBot(request: BotCreateRequest): Promise<Bot> {
  const response = await api.post<Bot>("/bots", request);
  return response.data;
}

export async function updateBot(id: string, request: BotUpdateRequest): Promise<Bot> {
  const response = await api.patch<Bot>(`/bots/${id}`, request);
  return response.data;
}

export type BotCommand = "start" | "pause" | "resume" | "stop";

export async function commandBot(
  id: string,
  command: BotCommand,
  scope: { account_id: string; mode: BotMode },
): Promise<Bot> {
  const response = await api.post<Bot>(`/bots/${id}/${command}`, scope);
  return response.data;
}

export async function listTrades(limit = 20): Promise<Trade[]> {
  const response = await api.get<Trade[]>("/trades", { params: { limit } });
  return response.data;
}

export async function listStrategies(): Promise<Strategy[]> {
  const response = await api.get<Strategy[]>("/strategies");
  return response.data;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>("/health");
  return response.data;
}
