'use client';
import Link from 'next/link';
import {
  dateLabel,
  moneyLabel,
  object,
  priceLabel,
  rLabel,
  text,
} from './shared';
import type { Json } from './shared';
import { useDisplayTimeZone } from '../../app/providers';
export function TradesTable({
  id,
  trades,
  error,
  retry,
}: {
  id: string;
  trades: unknown[];
  error?: string;
  retry?: () => void;
}) {
  const { timeZone } = useDisplayTimeZone();
  return error ? (
    <p role="status" className="text-atlas-negative">
      {error}
    </p>
  ) : trades.length ? (
    <div className="mt-4 overflow-x-auto rounded-lg border border-atlas-border bg-atlas-surface">
      <table className="w-full min-w-[760px] text-left text-sm">
        <caption className="sr-only">Experiment Trades</caption>
        <thead className="border-b border-atlas-border bg-atlas-surface-hover text-xs text-atlas-foreground-muted">
          <tr>
            {[
              'Trade',
              'Direction',
              'Opened',
              'Closed',
              'Entry',
              'Exit',
              'Net P&L',
              'R',
              'Result',
            ].map((h) => (
              <th key={h} className="px-4 py-3">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-atlas-border">
          {trades.map((raw, index) => {
            const t = object(raw);
            const seq = Number(text(t.sequence_number, String(index + 1)));
            return (
              <tr key={seq}>
                <td className="px-4 py-3">
                  <Link
                    className="font-medium text-atlas-primary hover:underline"
                    href={`/experiments/${id}/trades/${seq}`}
                  >
                    Trade {seq}
                  </Link>
                </td>
                <td className="px-4 py-3">{text(t.direction)}</td>
                <td className="px-4 py-3">
                  {dateLabel(t.opened_at, timeZone)}
                </td>
                <td className="px-4 py-3">
                  {dateLabel(t.closed_at, timeZone)}
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {priceLabel(t.entry_price)}
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {priceLabel(t.exit_price)}
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {moneyLabel(t.net_pnl)}
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {rLabel(t.r_multiple)}
                </td>
                <td className="px-4 py-3">
                  {t.ambiguous ? 'Ambiguous' : text(t.exit_reason)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  ) : (
    <div className="mt-4 rounded-lg border border-dashed border-atlas-control-border p-8 text-center text-sm text-atlas-foreground-muted">
      No executed Trades for this Experiment.
    </div>
  );
}
