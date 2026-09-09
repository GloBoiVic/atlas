'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, LoaderCircle } from 'lucide-react';

export type ReadState<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; error: unknown };

export function useReadResource<T>(loader: () => Promise<T>) {
  const [state, setState] = useState<ReadState<T>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.resolve()
      .then(loader)
      .then(
        (data) => {
          if (active) setState({ status: 'ready', data });
        },
        (error: unknown) => {
          if (active) setState({ status: 'error', error });
        },
      );
    return () => {
      active = false;
    };
  }, [attempt, loader]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((value) => value + 1);
  }, []);

  return { state, retry };
}

export function LoadingState({ label }: { label: string }) {
  return (
    <p
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 text-sm text-atlas-foreground-muted"
    >
      <LoaderCircle aria-hidden className="size-4 animate-spin" />
      Loading {label}…
    </p>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="status"
      className="border-l-2 border-atlas-control-border pl-3 text-sm text-atlas-foreground-muted"
    >
      {children}
    </p>
  );
}

export function UnavailableState({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="status"
      className="border-l-2 border-atlas-warning pl-3 text-sm text-atlas-warning"
    >
      {children}
    </p>
  );
}

export function ReadError({
  error,
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  const apiError =
    error &&
    typeof error === 'object' &&
    'code' in error &&
    typeof error.code === 'string'
      ? (error as { code: string; message?: unknown })
      : null;
  const message =
    (typeof apiError?.message === 'string' ? apiError.message : undefined) ??
    (error instanceof Error
      ? error.message
      : 'Atlas could not complete this read request.');

  return (
    <div
      role="alert"
      className="flex items-start gap-3 border-l-2 border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
    >
      <AlertCircle aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div>
        <p>{message}</p>
        {apiError && (
          <p className="mt-1 font-mono text-xs">Code: {apiError.code}</p>
        )}
        <button
          type="button"
          onClick={retry}
          className="mt-3 font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-focus-ring focus-visible:ring-offset-2"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
