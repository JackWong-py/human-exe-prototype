import * as React from "react";

import { cn } from "@/lib/utils";

// `flex flex-col` is part of the base on purpose: StatCard overrides it with `flex-row`
// to lay its icon and text out in a row.
export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        "flex flex-col gap-6 rounded-2xl border border-border bg-card py-6 text-card-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }) {
  return <div className={cn("flex flex-col gap-1 px-6", className)} {...props} />;
}

export function CardTitle({ className, ...props }) {
  return <h3 className={cn("text-base font-semibold leading-none", className)} {...props} />;
}

export function CardDescription({ className, ...props }) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function CardContent({ className, ...props }) {
  return <div className={cn("px-6", className)} {...props} />;
}

export function CardFooter({ className, ...props }) {
  return <div className={cn("flex items-center px-6 pt-4", className)} {...props} />;
}
