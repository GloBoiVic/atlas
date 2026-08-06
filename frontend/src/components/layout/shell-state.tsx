import type { ReactNode } from "react";

interface ShellStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function ShellLoading(): React.ReactElement {
  return (
    <div className="flex min-h-48 items-center justify-center p-atlas-6" role="status" aria-live="polite">
      <p className="text-atlas-sm text-atlas-fg-secondary">Loading Atlas…</p>
    </div>
  );
}

export function ShellError({ title, description, action }: ShellStateProps): React.ReactElement {
  return (
    <section className="border border-atlas-border rounded-atlas-md bg-atlas-bg-elevated p-atlas-6" role="alert">
      <h1 className="text-atlas-xl font-atlas-semibold tracking-atlas-tight text-atlas-fg">{title}</h1>
      <p className="mt-atlas-2 text-atlas-sm leading-atlas-normal text-atlas-fg-secondary">{description}</p>
      {action ? <div className="mt-atlas-4">{action}</div> : null}
    </section>
  );
}

export function PagePlaceholder({ title, description }: ShellStateProps): React.ReactElement {
  return (
    <section className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12">
      <h1 className="text-atlas-3xl font-atlas-semibold tracking-atlas-tight text-atlas-fg">{title}</h1>
      <p className="mt-atlas-2 max-w-prose text-atlas-md leading-atlas-normal text-atlas-fg-secondary">
        {description}
      </p>
    </section>
  );
}
