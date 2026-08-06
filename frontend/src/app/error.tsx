"use client";

import { ShellError } from "@/components/layout/shell-state";
import { Button } from "@/components/ui/button";

export default function Error({ reset }: { reset: () => void }): React.ReactElement {
  return (
    <div className="mx-auto max-w-atlas px-atlas-page-gutter py-atlas-12">
      <ShellError
        title="Atlas could not load this view"
        description="The page encountered an unexpected error. Try again before taking any action."
        action={
          <Button type="button" variant="outline" onClick={reset}>
            Try again
          </Button>
        }
      />
    </div>
  );
}
