import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider } from "@/auth/AuthProvider";
import { RequireAuth } from "@/auth/RequireAuth";
import { AppShell } from "@/components/app-shell";
import { RouteBoundary } from "@/components/route-boundary";
import { Skeleton } from "@/components/ui/skeleton";

const LoginPage = lazy(() => import("@/pages/login-page"));
const OverviewPage = lazy(() => import("@/pages/overview-page"));
const AccountsPage = lazy(() => import("@/pages/accounts-page"));
const MembersPage = lazy(() => import("@/pages/members-page"));
const UsagePage = lazy(() => import("@/pages/usage-page"));
const LogsPage = lazy(() => import("@/pages/logs-page"));
const SettingsPage = lazy(() => import("@/pages/settings-page"));
const NotFoundPage = lazy(() => import("@/pages/not-found-page"));

function ShellFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Skeleton className="h-6 w-40" />
    </div>
  );
}

const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <RouteBoundary fallbackHeight={240}>
        <LoginPage />
      </RouteBoundary>
    ),
  },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      {
        index: true,
        element: (
          <RouteBoundary fallbackHeight={260}>
            <OverviewPage />
          </RouteBoundary>
        ),
      },
      {
        path: "accounts",
        element: (
          <RouteBoundary>
            <AccountsPage />
          </RouteBoundary>
        ),
      },
      {
        path: "members",
        element: (
          <RouteBoundary>
            <MembersPage />
          </RouteBoundary>
        ),
      },
      {
        path: "usage",
        element: (
          <RouteBoundary>
            <UsagePage />
          </RouteBoundary>
        ),
      },
      {
        path: "logs",
        element: (
          <RouteBoundary>
            <LogsPage />
          </RouteBoundary>
        ),
      },
      {
        path: "settings",
        element: (
          <RouteBoundary>
            <SettingsPage />
          </RouteBoundary>
        ),
      },
    ],
  },
  {
    path: "*",
    element: (
      <RouteBoundary fallbackHeight={160}>
        <NotFoundPage />
      </RouteBoundary>
    ),
  },
]);

export function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<ShellFallback />}>
        <RouterProvider router={router} />
      </Suspense>
      <Toaster position="bottom-right" richColors closeButton />
    </AuthProvider>
  );
}
