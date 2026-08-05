import type { ReactElement } from "react";

import { BacktestStatus } from "@/lib/api";

export default function StatusBadge({ status }: { status: BacktestStatus }): ReactElement {
  const styles: Record<BacktestStatus, string> = {
    pending: "bg-atlas-warn-dim text-atlas-warn",
    running: "bg-atlas-accent-dim text-atlas-accent",
    completed: "bg-atlas-positive-dim text-atlas-positive",
    failed: "bg-atlas-negative-dim text-atlas-negative",
    cancelled: "bg-atlas-bg-elevated text-atlas-fg-secondary",
  };
  // 10px horizontal padding keeps the compact status pill balanced; no Atlas 2.5 token exists.
  return (
    <span className={`rounded-atlas-pill px-[10px] py-atlas-1 text-atlas-xs font-atlas-semibold leading-atlas-tight ${styles[status]}`}>
      {status}
    </span>
  );
}
