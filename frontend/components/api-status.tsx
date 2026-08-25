'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react';
import { atlasApi } from '../lib/api-client';

export function ApiStatus() {
  const [state, setState] = useState<'checking' | 'connected' | 'unavailable'>(
    'checking',
  );
  const check = useCallback(() => {
    setState('checking');
    atlasApi.ready().then(
      () => setState('connected'),
      () => setState('unavailable'),
    );
  }, []);

  useEffect(() => {
    let active = true;
    atlasApi.ready().then(
      () => active && setState('connected'),
      () => active && setState('unavailable'),
    );
    return () => {
      active = false;
    };
  }, []);

  if (state === 'checking') {
    return (
      <span className="status status-muted">
        <LoaderCircle aria-hidden className="size-3.5 animate-spin" /> Checking
        API
      </span>
    );
  }
  if (state === 'unavailable') {
    return (
      <span className="status status-danger" role="status">
        <AlertCircle aria-hidden className="size-3.5" /> API unavailable
        <button
          className="ml-1 underline underline-offset-2 focus-visible:outline-none"
          onClick={check}
        >
          Retry
        </button>
      </span>
    );
  }
  return (
    <span className="status status-primary" role="status">
      <CheckCircle2 aria-hidden className="size-3.5 text-atlas-positive" />{' '}
      PAPER · connected
    </span>
  );
}
