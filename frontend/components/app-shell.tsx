'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  BarChart3,
  Database,
  Layers3,
  Settings2,
} from 'lucide-react';
import { ApiStatus } from './api-status';
import { DISPLAY_TIME_ZONES } from '../lib/time';
import { useDisplayTimeZone } from '../app/providers';

const navigation = [
  { label: 'Overview', href: '/', icon: Activity },
  { label: 'Strategies', href: '/strategies', icon: Layers3 },
  { label: 'Experiments', href: '/experiments', icon: BarChart3 },
  { label: 'PAPER', href: '/paper', icon: Activity },
  { label: 'Data', href: '/data', icon: Database },
  { label: 'LIVE', href: '#', icon: Activity, disabled: true },
];

function isNavigationActive(pathname: string, href: string) {
  return href === '/' ? pathname === '/' : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { timeZone, setTimeZone } = useDisplayTimeZone();
  return (
    <div className="min-h-screen bg-atlas-background text-atlas-foreground">
      <header className="border-b border-atlas-border bg-atlas-surface">
        <div className="mx-auto flex min-h-16 max-w-[1440px] flex-wrap items-center justify-between gap-x-3 gap-y-2 px-6 py-2 sm:flex-nowrap sm:gap-6 sm:py-0 lg:px-10">
          <Link
            href="/"
            className="order-1 shrink-0 text-lg font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-focus-ring focus-visible:ring-offset-4"
          >
            Atlas
          </Link>
          <nav
            aria-label="Primary"
            className="order-3 flex min-w-0 flex-1 basis-full contain-paint items-center gap-1 overflow-x-auto sm:order-2 sm:basis-auto"
          >
            {navigation.map(({ label, href, icon: Icon, disabled }) =>
              disabled ? (
                <span
                  key={label}
                  aria-disabled="true"
                  className="nav-link nav-link-disabled shrink-0 whitespace-nowrap"
                  title={`${label} is planned for a later Atlas phase`}
                >
                  <Icon aria-hidden className="size-4" />
                  {label}
                  <span className="sr-only"> — future capability</span>
                </span>
              ) : (
                <Link
                  key={label}
                  href={href}
                  aria-current={
                    isNavigationActive(pathname, href) ? 'page' : undefined
                  }
                  className={`nav-link shrink-0 whitespace-nowrap ${isNavigationActive(pathname, href) ? 'nav-link-active' : ''}`}
                >
                  <Icon aria-hidden className="size-4" />
                  {label}
                </Link>
              ),
            )}
          </nav>
          <div className="order-2 flex shrink-0 items-center gap-4 text-sm sm:order-3">
            <ApiStatus />
            <label
              className="flex items-center gap-2 text-xs text-atlas-foreground-muted"
              title="Display timezone"
            >
              <Settings2 aria-hidden className="size-4" />
              <span className="sr-only">Display timezone</span>
              <select
                aria-label="Display timezone"
                value={timeZone}
                onChange={(e) => setTimeZone(e.target.value as typeof timeZone)}
                className="rounded-md border border-atlas-control-border bg-atlas-surface px-2 py-1.5 text-xs text-atlas-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-primary"
              >
                {DISPLAY_TIME_ZONES.map((zone) => (
                  <option key={zone}>{zone}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-12 lg:px-10">
        {children}
      </main>
    </div>
  );
}
