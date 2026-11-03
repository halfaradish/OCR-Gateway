import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { FieldError, Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";

const loginSchema = z.object({
  password: z.string().min(1, "请输入密码。"),
});

type LoginValues = z.infer<typeof loginSchema>;

const KNOWN_ERRORS: Record<string, string> = {
  UNAUTHORIZED: "密码不正确，请检查后重试。",
  RATE_LIMITED: "尝试次数过多，请 1 分钟后再试。",
};

export default function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { returnTo?: string } | null;
  const returnTo = state?.returnTo && state.returnTo.startsWith("/") ? state.returnTo : "/";

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { password: "" },
  });
  const submitError = form.formState.errors.root?.message;

  if (auth.status === "authed") {
    return <Navigate to={returnTo} replace />;
  }

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    try {
      await auth.login(values.password);
      navigate(returnTo, { replace: true });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? (KNOWN_ERRORS[error.code] ?? "登录失败，请重试。")
          : "无法连接网关，请确认服务正在运行。";
      form.setError("root", { message });
    }
  });

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-[min(360px,100%)]">
        <div className="mb-8">
          <p className="text-h2 font-medium text-navy">OCR Gateway</p>
          <p className="text-meta text-muted">管理面板 · 请登录</p>
        </div>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <div>
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              className="mt-1.5"
              aria-invalid={form.formState.errors.password ? true : undefined}
              {...form.register("password")}
            />
            <FieldError>{form.formState.errors.password?.message}</FieldError>
          </div>
          {submitError ? (
            <p role="alert" className="text-meta text-danger">
              {submitError}
            </p>
          ) : null}
          <Button
            type="submit"
            variant="primary"
            className="w-full"
            disabled={form.formState.isSubmitting}
          >
            {form.formState.isSubmitting ? "登录中…" : "登录"}
          </Button>
        </form>
      </div>
    </main>
  );
}
