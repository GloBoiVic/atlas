"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";

const primaryNavigation = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/strategies", label: "Strategies" },
  { href: "/backtests", label: "Backtests" },
  { href: "/paper", label: "Paper" },
  { href: "/testnet", label: "Testnet" },
  { href: "/trades", label: "Trades" },
  { href: "/journal", label: "Journal" },
  { href: "/analytics", label: "Analytics" },
] as const;

function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function TopNav(): React.ReactElement {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-atlas-sticky border-b border-atlas-border bg-atlas-bg">
      <div className="mx-auto flex h-atlas-topnav-height max-w-atlas items-center gap-atlas-6 px-atlas-page-gutter">
        <Link
          href="/dashboard"
          className="shrink-0 text-atlas-lg font-atlas-semibold tracking-atlas-tight text-atlas-fg transition-colors duration-atlas-base ease-atlas-out hover:text-atlas-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-accent/40"
        >
          Atlas
        </Link>

        <nav aria-label="Primary navigation" className="min-w-0 flex-1 overflow-x-auto">
          <ul className="flex min-w-max items-center gap-atlas-1">
            {primaryNavigation.map((item) => {
              const active = isActiveRoute(pathname, item.href);

              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "inline-flex min-h-11 items-center rounded-atlas px-atlas-3 text-atlas-sm font-atlas-medium transition-colors duration-atlas-base ease-atlas-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-accent/40",
                      active
                        ? "bg-atlas-accent-soft text-atlas-fg"
                        : "text-atlas-fg-secondary hover:bg-atlas-bg-elevated hover:text-atlas-fg",
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="flex shrink-0 items-center gap-atlas-4">
          <StatusBadge
            status="unavailable"
            label="Status unavailable"
            icon={<Activity className="size-3" aria-hidden="true" />}
          />
          <Link
            href="/settings"
            aria-current={isActiveRoute(pathname, "/settings") ? "page" : undefined}
            className={cn(
              "inline-flex min-h-11 items-center rounded-atlas px-atlas-3 text-atlas-sm font-atlas-medium transition-colors duration-atlas-base ease-atlas-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-accent/40",
              isActiveRoute(pathname, "/settings")
                ? "bg-atlas-accent-soft text-atlas-fg"
                : "text-atlas-fg-secondary hover:bg-atlas-bg-elevated hover:text-atlas-fg",
            )}
          >
            Settings
          </Link>
        </div>
      </div>
    </header>
  );
}
