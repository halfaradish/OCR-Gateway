import { cn } from "@/lib/utils";

export interface MetricItem {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "danger";
}

export function MetricStrip({ items, className }: { items: MetricItem[]; className?: string }) {
  return (
    <dl className={cn("grid grid-cols-2 gap-x-8 gap-y-6 md:grid-cols-4", className)}>
      {items.map((item) => (
        <div key={item.label}>
          <dt className="text-micro text-muted">{item.label}</dt>
          <dd
            className={cn(
              "mt-1 text-h1 font-medium tabular-nums",
              item.tone === "danger" ? "text-danger" : "text-ink",
            )}
          >
            {item.value}
          </dd>
          {item.hint ? <p className="mt-1 text-micro text-muted">{item.hint}</p> : null}
        </div>
      ))}
    </dl>
  );
}
