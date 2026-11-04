import type { ReactNode } from "react";

export function PageHeader({
  title,
  meta,
  description,
  actions,
}: {
  title: string;
  meta?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
      <div>
        <h1 className="text-h1 font-medium tracking-tight text-ink">{title}</h1>
        {meta ? (
          <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-meta text-muted">
            {meta}
          </div>
        ) : null}
        {description ? (
          <p className="mt-1 max-w-[76ch] text-meta text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}
