import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "@/auth/AuthProvider";
import { ErrorState } from "@/components/states";
import { Skeleton } from "@/components/ui/skeleton";

function BootScreen() {
  return (
    <div className="mx-auto flex min-h-screen w-[min(960px,100%-48px)] flex-col gap-6 py-24">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === "booting") return <BootScreen />;
  if (auth.status === "error") {
    return (
      <div className="mx-auto w-[min(560px,100%-48px)] py-24">
        <ErrorState
          title="无法连接到网关"
          description={auth.bootError ?? "请确认服务正在运行后重试。"}
          onRetry={auth.retryBoot}
        />
      </div>
    );
  }
  if (auth.status === "anon") {
    return (
      <Navigate
        to="/login"
        replace
        state={{ returnTo: `${location.pathname}${location.search}` }}
      />
    );
  }
  return <>{children}</>;
}
