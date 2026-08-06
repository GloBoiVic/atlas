import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Status = "unavailable" | "connected" | "disconnected" | "stale";

interface StatusBadgeProps {
  status: Status;
  label: string;
  icon?: ReactNode;
}

const statusClasses: Record<Status, string> = {
  unavailable: "bg-atlas-bg-elevated text-atlas-fg-secondary",
  connected: "bg-atlas-positive-dim text-atlas-positive",
  disconnected: "bg-atlas-negative-dim text-atlas-negative",
  stale: "bg-atlas-warn-dim text-atlas-warn",
};

export function StatusBadge({ status, label, icon }: StatusBadgeProps): React.ReactElement {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-atlas-2 rounded-atlas-pill border border-atlas-border px-atlas-3 py-atlas-1 text-atlas-xs font-atlas-medium",
        statusClasses[status],
      )}
      role="status"
    >
      {icon}
      <span>{label}</span>
    </span>
  );
}
