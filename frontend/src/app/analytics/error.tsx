"use client";

export default function Error({ reset }: { reset: () => void }): React.ReactElement {
  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-2xl rounded-atlas-md border border-atlas-border bg-atlas-surface p-atlas-6">
        <h1 className="text-atlas-xl font-atlas-semibold text-atlas-fg">Analytics unavailable</h1>
        <p className="mt-atlas-2 text-atlas-md text-atlas-fg-secondary">
          The analytics page could not be rendered. Try again when the API is available.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-atlas-5 min-h-atlas-10 rounded-atlas bg-atlas-accent px-atlas-4 py-atlas-2 text-atlas-sm font-atlas-semibold text-white focus:outline-none focus:ring-2 focus:ring-atlas-accent/40"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
