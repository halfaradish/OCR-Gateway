import { cn } from "@/lib/utils";
import { formatNumber } from "@/lib/time";

export interface QuotaRulerProps {
  used: number;
  limit: number | null;
  label: string;
  className?: string;
}

/**
 * The single memorable detail of the panel: a scale with 25/50/75 ticks and a marker
 * for the current position. The raw figures stay visible; the marker is clamped.
 */
export function QuotaRuler({ used, limit, label, className }: QuotaRulerProps) {
  const ratio = limit && limit > 0 ? Math.min(1, used / limit) : 0;
  const position = limit ? ratio * 100 : 0;
  const overLimit = limit !== null && used > limit;

  return (
    <div className={cn("min-w-[180px]", className)}>
      <div className="flex items-baseline justify-between text-micro text-muted">
        <span>{label}</span>
        <span className={cn("tabular-nums text-ink", overLimit && "text-danger")}>
          {formatNumber(used)}
          {limit === null ? " / 不限" : ` / ${formatNumber(limit)}`}
        </span>
      </div>
      <div className="relative mt-2 h-4" aria-hidden="true">
        <div className="absolute inset-x-0 top-2 h-px bg-line-strong/70" />
        <div
          className={cn(
            "absolute left-0 top-2 h-px",
            overLimit ? "bg-danger" : "bg-navy",
          )}
          style={{ width: `${position}%` }}
        />
        {[25, 50, 75].map((tick) => (
          <div
            key={tick}
            className="absolute top-[5px] h-1.5 w-px bg-line-strong/70"
            style={{ left: `${tick}%` }}
          />
        ))}
        {limit !== null && (
          <div
            className={cn(
              "absolute top-1 size-2 -translate-x-1/2 rounded-full",
              overLimit ? "bg-danger" : "bg-navy",
            )}
            style={{ left: `${position}%` }}
          />
        )}
      </div>
    </div>
  );
}
