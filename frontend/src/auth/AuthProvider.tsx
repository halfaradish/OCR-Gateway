import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiFetch, SessionExpiredError, sessionEvents } from "@/lib/api";
import type { LoginResponse, MeResponse } from "@/types";

type AuthStatus = "booting" | "authed" | "anon" | "error";

interface AuthContextValue {
  status: AuthStatus;
  username: string | null;
  bootError: string | null;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  retryBoot: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("booting");
  const [username, setUsername] = useState<string | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setStatus("booting");
    setBootError(null);
    try {
      const me = await apiFetch<MeResponse>("/api/admin/me");
      setUsername(me.username);
      setStatus("authed");
    } catch (error) {
      if (error instanceof SessionExpiredError) {
        setUsername(null);
        setStatus("anon");
        return;
      }
      setBootError(error instanceof Error ? error.message : "启动失败，请重试。");
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onExpired = () => {
      queryClient.clear();
      setUsername(null);
      setStatus("anon");
    };
    sessionEvents.addEventListener("expired", onExpired);
    return () => sessionEvents.removeEventListener("expired", onExpired);
  }, [queryClient]);

  const login = useCallback(
    async (password: string) => {
      await apiFetch<LoginResponse>("/api/admin/login", {
        method: "POST",
        body: { password },
        skipAuthRedirect: true,
      });
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(async () => {
    try {
      await apiFetch<void>("/api/admin/logout", { method: "POST" });
    } finally {
      queryClient.clear();
      setUsername(null);
      setStatus("anon");
    }
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, username, bootError, login, logout, retryBoot: () => void refresh() }),
    [status, username, bootError, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
