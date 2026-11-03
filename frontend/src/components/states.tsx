import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 py-10">
      <p className="text-body text-ink">{title}</p>
      {description ? <p className="text-meta text-muted">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
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
    <div className="flex flex-col items-start gap-2 py-10">
      <p className="text-body text-ink">{title}</p>
      {description ? <p className="text-meta text-muted">{description}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-sm border border-line bg-surface px-3 py-1.5 text-meta text-ink hover:bg-mist"
        >
          重试
        </button>
      ) : null}
    </div>
  );
}
