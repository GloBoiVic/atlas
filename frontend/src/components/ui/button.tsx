import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-atlas text-atlas-sm font-atlas-medium transition-colors duration-atlas-base ease-atlas-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-atlas-accent/40 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-atlas-accent text-white hover:bg-atlas-accent-dim",
        outline: "border border-atlas-border-strong text-atlas-fg hover:bg-atlas-bg-elevated",
        ghost: "text-atlas-fg-secondary hover:bg-atlas-bg-elevated hover:text-atlas-fg",
      },
      size: {
        default: "min-h-11 px-atlas-4 py-atlas-2",
        sm: "min-h-9 px-atlas-3 py-atlas-1",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps): React.ReactElement {
  return <button className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
