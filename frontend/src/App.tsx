import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
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

function AppRoutes() {
  const location = useLocation();
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RouteBoundary fallbackHeight={240}>
            <LoginPage />
          </RouteBoundary>
        }
      />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route
          index
          element={
            <RouteBoundary key={location.pathname} fallbackHeight={260}>
              <OverviewPage />
            </RouteBoundary>
          }
        />
        <Route
          path="accounts"
          element={
            <RouteBoundary key={location.pathname}>
              <AccountsPage />
            </RouteBoundary>
          }
        />
        <Route
          path="members"
          element={
            <RouteBoundary key={location.pathname}>
              <MembersPage />
            </RouteBoundary>
          }
        />
        <Route
          path="usage"
          element={
            <RouteBoundary key={location.pathname}>
              <UsagePage />
            </RouteBoundary>
          }
        />
        <Route
          path="logs"
          element={
            <RouteBoundary key={location.pathname}>
              <LogsPage />
            </RouteBoundary>
          }
        />
        <Route
          path="settings"
          element={
            <RouteBoundary key={location.pathname}>
              <SettingsPage />
            </RouteBoundary>
          }
        />
      </Route>
      <Route
        path="*"
        element={
          <RouteBoundary fallbackHeight={160}>
            <NotFoundPage />
          </RouteBoundary>
        }
      />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<ShellFallback />}>
          <AppRoutes />
        </Suspense>
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </BrowserRouter>
  );
}
