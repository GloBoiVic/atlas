'use client';
import { AlertCircle } from 'lucide-react';
import { ApiError } from '../../lib/api-client';
import { object, text, productNextAction, scalarFields } from './shared';
import type { Status } from './shared';
export function StatusBadge({ status }: { status: Status }) {
  const labels = {
    PENDING: 'Pending',
    RUNNING: 'Running',
    COMPLETED: 'Completed',
    FAILED: 'Failed',
  };
  return (
    <span
      className={`status rounded-full border border-atlas-border bg-atlas-surface-hover px-2.5 py-1 ${status === 'FAILED' ? 'text-atlas-negative' : status === 'COMPLETED' ? 'text-atlas-positive' : 'text-atlas-foreground-muted'}`}
    >
      <span aria-hidden>●</span>
      {labels[status]}
    </span>
  );
}
export function ErrorPanel({
  message,
  error,
  retry,
}: {
  message?: string;
  error?: unknown;
  retry?: () => void;
}) {
  const source = error ?? message ?? '';
  const api = source instanceof ApiError ? source : null;
  const fields = scalarFields(source);
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-start gap-3 rounded-lg border border-atlas-negative bg-atlas-negative-muted p-4 text-sm text-atlas-negative"
    >
      <AlertCircle aria-hidden className="mt-0.5 size-5 shrink-0" />
      <div className="flex-1">
        <p className="font-medium">
          {api && productNextAction(api)
            ? 'Action needed'
            : 'Request needs attention'}
        </p>
        <p className="mt-1">
          {api?.message ??
            (typeof source === 'string'
              ? source
              : source instanceof Error
                ? source.message
                : 'Atlas could not complete that request.')}
        </p>
        {api && <p className="mt-1 text-xs">Code: {api.code}</p>}
        {fields.length > 0 && (
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer font-medium">Details</summary>
            <dl className="mt-2 space-y-1">
              {fields.map(([key, value]) => (
                <div key={key}>
                  <dt className="inline font-medium">{key}: </dt>
                  <dd className="inline">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
        {retry && (
          <button onClick={retry} className="mt-3 font-medium underline">
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
