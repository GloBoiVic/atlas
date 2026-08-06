"use client";

import { Button } from "@/components/ui/button";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }): React.ReactElement {
  return <main className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12"><section className="rounded-atlas-md border border-atlas-border bg-atlas-bg-elevated p-atlas-6" role="alert"><h1 className="text-atlas-xl font-atlas-semibold">Dashboard unavailable</h1><p className="mt-atlas-2 text-atlas-sm text-atlas-fg-secondary">The dashboard route could not be rendered. No trading state has been assumed.</p><Button className="mt-atlas-4" variant="outline" onClick={reset}>Try again</Button></section></main>;
}
