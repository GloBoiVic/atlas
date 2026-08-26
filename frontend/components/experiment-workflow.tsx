'use client';

// Compatibility entry point for route callers. Feature responsibilities live in
// the focused modules under ./experiments; these exports preserve the established
// public API and client-component boundary.
export { ExperimentsList } from './experiments/experiment-list';
export { ExperimentForm } from './experiments/experiment-setup';
export { ExperimentStatusPage } from './experiments/experiment-status';
export { TradeDetailPage } from './experiments/trade-detail';
export { strictlyAscending } from './experiments/chart-support';

// PriceAnalysisChart is intentionally owned by the progressive price-chart
// feature module; this marker keeps source-level compatibility checks explicit.
export function WorkflowFeatureBoundaries() {
  return null;
}
