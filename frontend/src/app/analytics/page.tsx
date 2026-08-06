import { AnalyticsResponse, getAnalytics } from "@/lib/api";
import AnalyticsView from "@/app/analytics/analytics-view";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage(): Promise<React.ReactElement> {
  let initialAnalytics: AnalyticsResponse | null = null;
  let initialLoadError: string | undefined;

  try {
    initialAnalytics = await getAnalytics();
  } catch {
    initialLoadError = "Unable to load analytics.";
  }

  return (
    <AnalyticsView
      initialAnalytics={initialAnalytics}
      initialLoadError={initialLoadError}
    />
  );
}
