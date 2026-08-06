export default function Loading(): React.ReactElement {
  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-7xl" aria-busy="true" aria-label="Loading analytics">
        <div className="h-8 w-48 animate-pulse rounded-atlas bg-atlas-bg-elevated" />
        <div className="mt-atlas-8 h-32 animate-pulse rounded-atlas-md bg-atlas-surface" />
      </div>
    </main>
  );
}
