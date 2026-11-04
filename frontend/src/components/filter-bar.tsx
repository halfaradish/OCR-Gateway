import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** Compact filter group: one baseline, micro labels, so five controls read as one tool. */
export function FilterBar({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-wrap items-end gap-x-4 gap-y-3", className)}>
      {children}
    </div>
  );
}

export function FilterField({
  htmlFor,
  label,
  className,
  children,
}: {
  htmlFor: string;
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <Label htmlFor={htmlFor} className="text-micro font-normal text-muted">
        {label}
      </Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
