export default function SettingsPage(): React.ReactElement {
  return (
    <main className="min-h-screen bg-atlas-bg px-atlas-4 py-atlas-8 text-atlas-fg sm:px-atlas-6 lg:px-atlas-8">
      <div className="mx-auto max-w-atlas">
        <header className="border-b border-atlas-border pb-atlas-6"><p className="font-atlas-mono text-atlas-xs tracking-atlas-wide text-atlas-accent">CONFIGURATION BOUNDARY</p><h1 className="mt-atlas-2 text-atlas-3xl font-atlas-semibold tracking-atlas-tight">Settings</h1><p className="mt-atlas-2 max-w-2xl text-atlas-md text-atlas-fg-secondary">Atlas only exposes settings that are backed by an authenticated API contract.</p></header>
        <section className="mt-atlas-8 rounded-atlas-md border border-atlas-border bg-atlas-surface p-atlas-6" role="status"><h2 className="text-atlas-xl font-atlas-semibold">Settings are not available yet</h2><p className="mt-atlas-3 max-w-2xl text-atlas-md leading-atlas-normal text-atlas-fg-secondary">No supported settings or configuration read/write endpoint is deployed for this slice. Risk, account, broker, and bot configuration remain server-owned. This page will not invent editable controls or persist local-only trading configuration.</p><p className="mt-atlas-4 rounded-atlas border border-atlas-border bg-atlas-bg-elevated p-atlas-4 text-atlas-sm text-atlas-warn">Backend prerequisite: define and deploy a typed, scoped settings contract before Atlas can display or edit settings.</p></section>
      </div>
    </main>
  );
}
