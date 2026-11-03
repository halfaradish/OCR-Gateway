import { Component, Suspense, type ErrorInfo, type ReactNode } from "react";

import { ErrorState } from "@/components/states";
import { Skeleton } from "@/components/ui/skeleton";

interface BoundaryState {
  error: Error | null;
}

class Boundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("route boundary", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <ErrorState
          title="页面加载失败"
          description={this.state.error.message}
          onRetry={() => window.location.reload()}
        />
      );
    }
    return this.props.children;
  }
}

/** Bounds each route (white screen radius = one page) and keeps the fallback at final size. */
export function RouteBoundary({
  children,
  fallbackHeight = 320,
}: {
  children: ReactNode;
  fallbackHeight?: number;
}) {
  return (
    <Boundary>
      <Suspense
        fallback={
          <div className="space-y-4" aria-busy="true" aria-live="polite">
            <Skeleton className="h-9 w-56" />
            <Skeleton style={{ height: fallbackHeight }} className="w-full" />
          </div>
        }
      >
        {children}
      </Suspense>
    </Boundary>
  );
}
