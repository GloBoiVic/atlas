import type { ReactNode } from 'react';

export function Popover({ children }: { children: ReactNode }) {
  return <div className="relative">{children}</div>;
}

export function PopoverTrigger({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" {...props}>
      {children}
    </button>
  );
}

export function PopoverContent({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`absolute z-20 mt-2 rounded-md border border-atlas-border bg-atlas-surface p-3 shadow-lg ${className}`}
    >
      {children}
    </div>
  );
}
