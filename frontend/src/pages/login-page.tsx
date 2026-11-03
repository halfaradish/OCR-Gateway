import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FieldError, Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";

const KNOWN_ERRORS: Record<string, string> = {
  UNAUTHORIZED: "密码不正确，请检查后重试。",
  RATE_LIMITED: "尝试次数过多，请 1 分钟后再试。",
};

/**
 * Single-field form kept free of react-hook-form/zod on purpose: this is the panel's first
 * paint, and the form libraries would add ~40 kB gzip to that route (budget: 150 kB).
 */
export default function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { returnTo?: string } | null;
  const returnTo = state?.returnTo && state.returnTo.startsWith("/") ? state.returnTo : "/";

  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (auth.status === "authed") {
    return <Navigate to={returnTo} replace />;
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    if (!password.trim()) {
      setFieldError("请输入密码。");
      return;
    }
    setFieldError(null);
    setPending(true);
    try {
      await auth.login(password);
      navigate(returnTo, { replace: true });
    } catch (error) {
      setSubmitError(
        error instanceof ApiError
          ? (KNOWN_ERRORS[error.code] ?? "登录失败，请重试。")
          : "无法连接网关，请确认服务正在运行。",
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-[min(360px,100%)]">
        <div className="mb-8">
          <p className="text-h2 font-medium text-navy">OCR Gateway</p>
          <p className="text-meta text-muted">管理面板 · 请登录</p>
        </div>
        <form onSubmit={(event) => void onSubmit(event)} noValidate className="space-y-4">
          <div>
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              className="mt-1.5"
              value={password}
              aria-invalid={fieldError ? true : undefined}
              onChange={(event) => {
                setPassword(event.target.value);
                if (fieldError) setFieldError(null);
              }}
            />
            <FieldError>{fieldError}</FieldError>
          </div>
          {submitError ? (
            <p role="alert" className="text-meta text-danger">
              {submitError}
            </p>
          ) : null}
          <Button type="submit" variant="primary" className="w-full" disabled={pending}>
            {pending ? "登录中…" : "登录"}
          </Button>
        </form>
      </div>
    </main>
  );
}
