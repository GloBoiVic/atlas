import { BacktestRun, listBacktests } from "@/lib/api";
import BacktestsView from "@/app/backtests/backtests-view";

export const dynamic = "force-dynamic";

export default async function BacktestsPage() {
  let runs: BacktestRun[] = [];
  let initialLoadError: string | undefined;
  try {
    runs = await listBacktests();
  } catch {
    initialLoadError = "Unable to load backtests.";
  }
  return <BacktestsView initialRuns={runs} initialLoadError={initialLoadError} />;
}
