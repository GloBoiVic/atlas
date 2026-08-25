'use client';

import { Toaster } from 'sonner';
import { createContext, useContext, useEffect, useState } from 'react';
import { DEFAULT_DISPLAY_TIME_ZONE, DISPLAY_TIME_ZONE_STORAGE_KEY, type DisplayTimeZone, isDisplayTimeZone } from '../lib/time';

const DisplayTimeZoneContext = createContext<{ timeZone: DisplayTimeZone; setTimeZone: (zone: DisplayTimeZone) => void }>({ timeZone: DEFAULT_DISPLAY_TIME_ZONE, setTimeZone: () => undefined });

export function useDisplayTimeZone() { return useContext(DisplayTimeZoneContext); }

export function Providers({ children }: { children: React.ReactNode }) {
  const [timeZone, setTimeZoneState] = useState<DisplayTimeZone>(DEFAULT_DISPLAY_TIME_ZONE);
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(DISPLAY_TIME_ZONE_STORAGE_KEY);
      // Hydration intentionally updates the preference after the first render.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (isDisplayTimeZone(stored)) setTimeZoneState(stored);
    } catch {
      // Storage may be disabled or unavailable; Chicago remains the safe default.
    }
  }, []);
  const setTimeZone = (zone: DisplayTimeZone) => {
    setTimeZoneState(zone);
    try { window.localStorage.setItem(DISPLAY_TIME_ZONE_STORAGE_KEY, zone); } catch { /* safe fallback */ }
  };
  return (
    <DisplayTimeZoneContext.Provider value={{ timeZone, setTimeZone }}>
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          style: {
            background: 'var(--atlas-color-surface)',
            border: '1px solid var(--atlas-color-border)',
            color: 'var(--atlas-color-foreground)',
          },
        }}
      />
      <>{children}</>
    </DisplayTimeZoneContext.Provider>
  );
}
