import type { ReactElement } from "react";

import { AlertCircle, Clock3, XCircle } from "lucide-react";
import { BacktestStatus } from "@/lib/api";

export default function StatusMessage({ status, error }: { status: BacktestStatus; error?: string | null }): ReactElement | null {
  if (status === "completed") return null;
  const Icon = status === "failed" ? XCircle : status === "cancelled" ? AlertCircle : Clock3;
  const text = error || (status === "running" ? "The replay is in progress." : status === "pending" ? "Queued for replay." : "This run was cancelled.");
  return <div className="flex items-start gap-atlas-3 rounded-atlas border border-atlas-border bg-atlas-bg-elevated p-atlas-4 text-atlas-md leading-atlas-normal text-atlas-fg-secondary" role="status"><Icon className="mt-[2px] size-4 shrink-0 text-atlas-accent" aria-hidden="true" /><span>{text}</span></div>;
}
