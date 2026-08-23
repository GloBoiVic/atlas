import Link from 'next/link';
import {
  Activity,
  BarChart3,
  BookOpen,
  Database,
  Layers3,
  Settings2,
} from 'lucide-react';
import { ApiStatus } from './api-status';

const navigation = [
  { label: 'Dashboard', href: '#', icon: Activity, disabled: true },
  { label: 'Strategies', href: '#', icon: Layers3, disabled: true },
  { label: 'Experiments', href: '/experiments', icon: BarChart3, active: true },
  { label: 'Deployments', href: '#', icon: Activity, disabled: true },
  { label: 'Journal', href: '#', icon: BookOpen, disabled: true },
  { label: 'Data', href: '#', icon: Database, disabled: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--atlas-background)] text-[var(--atlas-ink)]">
      <header className="border-b border-slate-200 bg-white">
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
                    className={`nav-link ${active ? 'nav-link-active' : ''} ${disabled ? 'nav-link-disabled' : ''}`}
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
            <button
              aria-label="Settings"
              className="rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
            >
              <Settings2 aria-hidden className="size-4" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-12 lg:px-10">
        {children}
      </main>
    </div>
  );
}
