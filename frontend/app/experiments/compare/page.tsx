import { Suspense } from 'react';
import { ExperimentComparisonPage } from '../../../components/experiment-comparison';

export default function Page() {
  return (
    <Suspense
      fallback={
        <p className="bg-atlas-background p-8 text-sm text-atlas-foreground-muted">
          Loading comparison…
        </p>
      }
    >
      <ExperimentComparisonPage />
    </Suspense>
  );
}
