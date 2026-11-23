"use client";
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded border text-xs font-medium transition-colors disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        default: "border-line-strong bg-surface-raised text-ink hover:border-accent/50 hover:text-accent",
        accent: "border-accent bg-accent text-accent-foreground hover:bg-accent/90",
        ghost: "border-transparent text-ink-muted hover:bg-surface-raised hover:text-ink",
        outline: "border-line-strong text-ink-muted hover:border-accent/50 hover:text-ink",
      },
      size: { sm: "h-7 px-2", md: "h-8 px-3", icon: "h-7 w-7" },
    },
    defaultVariants: { variant: "default", size: "sm" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
  },
);
Button.displayName = "Button";
export { buttonVariants };
