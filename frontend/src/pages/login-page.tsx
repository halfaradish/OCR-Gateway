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

const CAPABILITIES = [
  ["路由", "按优先级与 EWMA 延迟自动选号，失败切换厂商"],
  ["配额", "账号日/月/总量与 Key 日限额、RPM 统一记账"],
  ["台账", "请求日志只存元数据，不落 OCR 原文"],
];

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
    <main className="flex min-h-screen flex-col bg-paper lg:flex-row">
      <aside className="hidden w-[44%] max-w-[520px] flex-col bg-navy px-10 py-12 lg:flex">
        <div>
          <p className="text-[19px] font-medium tracking-tight text-white">OCR Gateway</p>
          <p className="mt-1 text-micro text-white/55">管理面板</p>
        </div>
        <div className="my-auto py-16">
          <p className="max-w-[22ch] text-[30px] font-medium leading-[1.35] text-white">
            把两家 OCR
            <br />
            当成一条通路来管理。
          </p>
          <dl className="mt-10 max-w-[380px] space-y-4">
            {CAPABILITIES.map(([label, value]) => (
              <div key={label} className="flex gap-4 border-t border-white/10 pt-3">
                <dt className="w-10 shrink-0 text-micro text-white/55">{label}</dt>
                <dd className="text-meta text-white/75">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </aside>

      <div className="bg-navy px-5 py-5 lg:hidden">
        <p className="text-[17px] font-medium tracking-tight text-white">OCR Gateway</p>
        <p className="mt-0.5 text-micro text-white/55">管理面板</p>
      </div>

      <div className="flex flex-1 items-center justify-center px-5 py-12">
        <div className="w-full max-w-[340px]">
          <h1 className="text-h1 font-medium tracking-tight text-ink">登录</h1>
          <p className="mt-1 text-meta text-muted">使用管理员密码进入控制面板。</p>
          <form onSubmit={(event) => void onSubmit(event)} noValidate className="mt-8 space-y-4">
            <div>
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                className="mt-1.5"
                value={password}
                aria-invalid={fieldError ? true : undefined}
                aria-describedby={fieldError ? "password-error" : undefined}
                onChange={(event) => {
                  setPassword(event.target.value);
                  if (fieldError) setFieldError(null);
                }}
              />
              <FieldError id="password-error">{fieldError}</FieldError>
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
      </div>
    </main>
  );
}
