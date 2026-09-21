import * as React from "react";

import { cn } from "@/lib/utils";

// Minimal controlled Tabs: the parent owns `value` and gets told about clicks via
// `onValueChange`. Context passes those down so TabsTrigger stays a simple child.
const TabsContext = React.createContext({ value: undefined, onValueChange: () => {} });

export function Tabs({ className, value, onValueChange = () => {}, ...props }) {
  const ctx = React.useMemo(() => ({ value, onValueChange }), [value, onValueChange]);
  return (
    <TabsContext.Provider value={ctx}>
      <div className={cn("flex flex-col gap-2", className)} {...props} />
    </TabsContext.Provider>
  );
}

export function TabsList({ className, ...props }) {
  return (
    <div
      role="tablist"
      className={cn("inline-flex w-fit items-center gap-1 rounded-lg bg-muted p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, value, children, ...props }) {
  const { value: selected, onValueChange } = React.useContext(TabsContext);
  const active = selected === value;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={() => onValueChange(value)}
      className={cn(
        "rounded-md px-3 py-1.5 text-xs font-semibold transition",
        "focus-visible:ring-ring/60 focus-visible:outline-none focus-visible:ring-2",
        active ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function TabsContent({ className, value, ...props }) {
  const { value: selected } = React.useContext(TabsContext);
  if (selected !== value) return null;
  return <div role="tabpanel" className={cn("flex-1", className)} {...props} />;
}
