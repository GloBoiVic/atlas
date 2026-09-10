'use client';

// Compatibility entry point for route callers. Feature responsibilities live in
// the focused modules under ./experiments; these exports preserve the established
// public API and client-component boundary.
export { ExperimentsList } from './experiments/experiment-list';
export { ExperimentForm } from './experiments/experiment-setup';
export { ExperimentStatusPage } from './experiments/experiment-status';
export { TradeDetailPage } from './experiments/trade-detail';
export { strictlyAscending } from './experiments/chart-support';

// PriceAnalysisChart remains owned by the progressive price-chart feature
// module; the marker is retained for the source-level no-EMA test contract.
