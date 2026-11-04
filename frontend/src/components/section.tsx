import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Section hierarchy is carried by type and surface, never by identical cards:
 * `primary` gets the page's single white screen; `secondary` stays on the paper.
 */
export function Section({
  id,
  title,
  meta,
  action,
  level = "secondary",
  className,
  children,
}: {
  id: string;
  title: string;
  meta?: ReactNode;
  action?: ReactNode;
  level?: "primary" | "secondary";
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className={cn(level === "primary" ? "mt-12" : "mt-10", className)}
    >
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2
            id={id}
            className={cn(
              "font-medium text-ink",
              level === "primary" ? "text-h2" : "text-[15px]",
            )}
          >
            {title}
          </h2>
          {meta ? <p className="text-micro text-muted">{meta}</p> : null}
        </div>
        {action ? <div className="flex items-center gap-4">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

/** The page's one white screen: a thin rule around content, no shadow, no decoration. */
export function Panel({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("overflow-hidden rounded-md border border-line bg-surface", className)}>
      {children}
    </div>
  );
}

/** Toolbar row inside a panel: filters left, counts / actions right. */
export function PanelToolbar({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-line px-5 py-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
