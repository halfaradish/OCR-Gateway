import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface MetricItem {
  label: string;
  value: string;
  hint?: ReactNode;
  tone?: "default" | "danger";
}

/**
 * The first-glance readout. One lead figure carries the page; the other three are
 * supporting readouts, separated by rules instead of cards.
 */
export function WatchBand({
  lead,
  items,
  className,
}: {
  lead: MetricItem;
  items: MetricItem[];
  className?: string;
}) {
  return (
    <section
      aria-label="今日指标"
      className={cn(
        "rounded-md border border-line border-t-2 border-t-navy bg-mist/70 px-6 py-6 md:px-8",
        className,
      )}
    >
      <div className="grid grid-cols-2 gap-x-6 gap-y-6 md:grid-cols-[1.35fr_repeat(3,1fr)] md:gap-x-0">
        <div className="col-span-2 md:col-span-1 md:pr-8">
          <p className="text-micro font-medium text-muted">{lead.label}</p>
          <p
            className={cn(
              "mt-2 text-display font-medium tabular-nums",
              lead.tone === "danger" ? "text-danger" : "text-ink",
            )}
          >
            {lead.value}
          </p>
          {lead.hint ? <p className="mt-2 text-meta text-muted">{lead.hint}</p> : null}
        </div>
        {items.map((item) => (
          <div
            key={item.label}
            className="border-t border-line pt-4 md:border-l md:border-t-0 md:pl-8 md:pt-0"
          >
            <p className="text-micro font-medium text-muted">{item.label}</p>
            <p
              className={cn(
                "mt-2 text-lead font-medium tabular-nums",
                item.tone === "danger" ? "text-danger" : "text-ink",
              )}
            >
              {item.value}
            </p>
            {item.hint ? <p className="mt-1.5 text-micro text-muted">{item.hint}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
