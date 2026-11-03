import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={cn("animate-pulse rounded-sm bg-mist", className)}
      style={style}
      aria-hidden="true"
    />
  );
}
