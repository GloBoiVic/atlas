"use client";

export default function JournalError({ reset }: { reset: () => void }): React.ReactElement {
  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-2xl rounded-atlas-md border border-atlas-border bg-atlas-surface p-atlas-6">
        <h1 className="text-atlas-2xl font-atlas-semibold text-atlas-fg">Journal unavailable</h1>
        <p className="mt-atlas-2 text-atlas-md text-atlas-fg-secondary">Atlas could not render the journal. Try again when the API is available.</p>
        <button type="button" onClick={reset} className="mt-atlas-5 min-h-atlas-10 rounded-atlas border border-atlas-border px-atlas-4 py-atlas-2 text-atlas-md font-atlas-semibold text-atlas-fg hover:bg-atlas-bg-elevated focus:outline-none focus:ring-2 focus:ring-atlas-accent/30">Try again</button>
      </div>
    </main>
  );
}
