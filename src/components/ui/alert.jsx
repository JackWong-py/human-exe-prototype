import * as React from "react";

import { cn } from "@/lib/utils";

const VARIANTS = {
  default: "border-border bg-card text-card-foreground",
  destructive: "border-destructive/40 bg-destructive/10 text-destructive",
};

export function Alert({ className, variant = "default", ...props }) {
  return (
    <div
      role="alert"
      className={cn("rounded-xl border px-4 py-3 text-sm", VARIANTS[variant] ?? VARIANTS.default, className)}
      {...props}
    />
  );
}

export function AlertTitle({ className, ...props }) {
  return <div className={cn("mb-1 font-semibold leading-none", className)} {...props} />;
}

export function AlertDescription({ className, ...props }) {
  return <div className={cn("text-sm opacity-90", className)} {...props} />;
}
