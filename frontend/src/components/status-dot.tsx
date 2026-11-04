import { cn } from "@/lib/utils";

const STATE_LABELS: Record<string, string> = {
  active: "可用",
  cooling: "冷却中",
  invalid: "凭证失效",
  quota_exhausted: "配额耗尽",
  disabled: "已禁用",
  unknown: "未知",
};

const STATE_TONES: Record<string, string> = {
  active: "bg-success",
  cooling: "bg-warn",
  invalid: "bg-danger",
  quota_exhausted: "bg-danger",
  disabled: "bg-muted",
  unknown: "bg-muted",
};

export function stateLabel(state: string): string {
  return STATE_LABELS[state] ?? state;
}

/** Status is never conveyed by color alone: a 6px dot plus the state name. */
export function StatusDot({ state, label }: { state: string; label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-meta">
      <span
        className={cn("size-1.5 rounded-full", STATE_TONES[state] ?? STATE_TONES.unknown)}
        aria-hidden="true"
      />
      <span>{label ?? stateLabel(state)}</span>
    </span>
  );
}
