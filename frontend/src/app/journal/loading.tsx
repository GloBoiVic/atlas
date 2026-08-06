export default function JournalLoading(): React.ReactElement {
  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-7xl animate-pulse">
        <div className="h-10 w-48 rounded-atlas bg-atlas-bg-elevated" />
        <div className="mt-atlas-3 h-5 max-w-xl rounded-atlas bg-atlas-bg-elevated" />
        <div className="mt-atlas-8 h-96 rounded-atlas-md border border-atlas-border bg-atlas-surface" />
      </div>
    </main>
  );
}
