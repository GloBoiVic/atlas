import { Suspense } from 'react';
import { ExperimentComparisonPage } from '../../../components/experiment-comparison';

export default function Page() {
  return (
    <Suspense
      fallback={
        <p className="p-8 text-sm text-slate-600">Loading comparison…</p>
      }
    >
      <ExperimentComparisonPage />
    </Suspense>
  );
}
