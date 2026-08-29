import { Suspense } from 'react';
import { ExperimentForm } from '../../../components/experiment-workflow';

export default function NewExperimentPage() {
  return (
    <Suspense
      fallback={
        <p className="bg-atlas-background p-8 text-sm text-atlas-foreground-muted">
          Loading Experiment setup…
        </p>
      }
    >
      <ExperimentForm />
    </Suspense>
  );
}
