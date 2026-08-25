'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  BarChart3,
  BookOpen,
  Database,
  Layers3,
  Settings2,
} from 'lucide-react';
import { ApiStatus } from './api-status';
import { DISPLAY_TIME_ZONES } from '../lib/time';
import { useDisplayTimeZone } from '../app/providers';

const navigation = [
  { label: 'Dashboard', href: '#', icon: Activity, disabled: true },
  { label: 'Strategies', href: '/strategies', icon: Layers3 },
  { label: 'Experiments', href: '/experiments', icon: BarChart3, active: true },
  { label: 'Deployments', href: '#', icon: Activity, disabled: true },
  { label: 'Journal', href: '#', icon: BookOpen, disabled: true },
  { label: 'Data', href: '#', icon: Database, disabled: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { timeZone, setTimeZone } = useDisplayTimeZone();
  return (
    <div className="min-h-screen bg-atlas-background text-atlas-foreground">
      <header className="border-b border-atlas-border bg-atlas-surface">
        <div className="mx-auto flex min-h-16 max-w-[1440px] items-center justify-between gap-6 px-6 lg:px-10">
          <div className="flex min-w-0 items-center gap-8">
            <Link
              href="/experiments"
              className="shrink-0 text-lg font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-4"
            >
              Atlas
            </Link>
            <nav
              aria-label="Primary"
              className="flex items-center gap-1 overflow-x-auto"
            >
              {navigation.map(
                ({ label, href, icon: Icon, active, disabled }) => (
                  <Link
                    key={label}
                    href={href}
                    aria-disabled={disabled}
                    tabIndex={disabled ? -1 : undefined}
                    className={`nav-link ${active || (href !== '#' && pathname.startsWith(href)) ? 'nav-link-active' : ''} ${disabled ? 'nav-link-disabled' : ''}`}
                  >
                    <Icon aria-hidden className="size-4" />
                    {label}
                  </Link>
                ),
              )}
            </nav>
          </div>
          <div className="flex shrink-0 items-center gap-4 text-sm">
            <ApiStatus />
            <label className="flex items-center gap-2 text-xs text-atlas-foreground-muted" title="Display timezone">
              <Settings2 aria-hidden className="size-4" />
              <span className="sr-only">Display timezone</span>
              <select aria-label="Display timezone" value={timeZone} onChange={(e) => setTimeZone(e.target.value as typeof timeZone)} className="rounded-md border border-atlas-control-border bg-atlas-surface px-2 py-1.5 text-xs text-atlas-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-primary">
                {DISPLAY_TIME_ZONES.map((zone) => <option key={zone}>{zone}</option>)}
              </select>
            </label>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-12 lg:px-10">
        <p className="mb-6 text-xs text-atlas-foreground-muted" role="status">Times shown in {timeZone}</p>
        {children}
      </main>
    </div>
  );
}
