import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
  compact = false,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "py-6" : "py-10"} role="status">
      <p className="text-body font-medium text-ink">{title}</p>
      {description ? (
        <p className="mt-1 max-w-[60ch] text-meta text-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = "数据未加载",
  description,
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="py-10" role="alert">
      <p className="text-body font-medium text-ink">{title}</p>
      {description ? (
        <p className="mt-1 max-w-[60ch] text-meta text-muted">{description}</p>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-sm border border-line-strong/70 bg-surface px-3 py-1.5 text-meta text-ink hover:bg-mist/60"
        >
          重试
        </button>
      ) : null}
    </div>
  );
}
