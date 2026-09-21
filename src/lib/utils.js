import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

// shadcn's helper for joining class names. (`shadcn init` normally creates this file.)
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
