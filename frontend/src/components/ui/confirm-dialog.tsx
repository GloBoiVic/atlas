"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  consequence: string;
  details: string[];
  confirmLabel: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({
  open,
  title,
  consequence,
  details,
  confirmLabel,
  busy = false,
  onCancel,
  onConfirm,
}: ConfirmDialogProps): React.ReactElement | null {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={onCancel}
      className="w-[min(92vw,32rem)] rounded-atlas-md border border-atlas-border bg-atlas-surface p-0 text-atlas-fg backdrop:bg-black/70"
      aria-labelledby="confirmation-title"
    >
      <div className="p-atlas-6">
        <h2 id="confirmation-title" className="text-atlas-xl font-atlas-semibold">
          {title}
        </h2>
        <div className="mt-atlas-5 rounded-atlas border border-atlas-border bg-atlas-bg-elevated p-atlas-4 text-atlas-sm">
          {details.map((detail) => <p key={detail} className="font-atlas-mono">{detail}</p>)}
        </div>
        <p className="mt-atlas-4 text-atlas-sm leading-atlas-normal text-atlas-warn">
          {consequence}
        </p>
        <div className="mt-atlas-6 flex justify-end gap-atlas-3">
          <Button type="button" variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" onClick={onConfirm} disabled={busy}>
            {busy ? "Confirming…" : confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
