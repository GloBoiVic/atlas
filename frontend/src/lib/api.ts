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
