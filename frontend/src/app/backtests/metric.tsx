import { ReactElement } from "react";

export default function Metric({ label, value, tone = "text-atlas-fg" }: { label: string; value: string; tone?: string }): ReactElement {
  return (
    <div className="border-b border-atlas-border py-atlas-3 last:border-0">
      <dt className="text-atlas-xs leading-atlas-snug text-atlas-fg-secondary">{label}</dt>
      <dd className={`mt-atlas-1 font-atlas-mono text-atlas-lg leading-atlas-snug ${tone}`}>{value}</dd>
    </div>
  );
}
