import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/page-header";
import { Panel, Section } from "@/components/section";
import { ErrorState } from "@/components/states";
import { StatusDot } from "@/components/status-dot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FieldError, Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ApiError, apiFetch } from "@/lib/api";
import { formatNumber } from "@/lib/time";
import { LeaveConfirmDialog, useUnsavedChanges } from "@/lib/unsaved-changes";
import type {
  LocalOcrStatus,
  QuotaTemplatesResponse,
  SettingsResponse,
  SettingsUpdateResponse,
} from "@/types";

const settingsSchema = z.object({
  cache_enabled: z.boolean(),
  cache_ttl_seconds: z
    .string()
    .regex(/^\d+$/, "缓存 TTL 必须是整数。")
    .refine((value) => Number(value) >= 60 && Number(value) <= 86400, "缓存 TTL 需在 60 到 86400 秒之间。"),
  cache_max_entries: z
    .string()
    .regex(/^\d+$/, "缓存容量必须是整数。")
    .refine((value) => Number(value) >= 10 && Number(value) <= 2000, "缓存容量需在 10 到 2000 条之间。"),
  request_deadline_ms: z
    .string()
    .regex(/^\d+$/, "请求总预算必须是整数。")
    .refine(
      (value) => Number(value) >= 1000 && Number(value) <= 20000,
      "请求总预算需在 1000 到 20000 毫秒之间。",
    ),
  default_timeout_ms: z
    .string()
    .regex(/^\d+$/, "账号默认超时必须是整数。")
    .refine(
      (value) => Number(value) >= 1000 && Number(value) <= 60000,
      "账号默认超时需在 1000 到 60000 毫秒之间。",
    ),
  local_ocr_enabled: z.boolean(),
});

type SettingsValues = z.infer<typeof settingsSchema>;

export default function SettingsPage() {
  const queryClient = useQueryClient();

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiFetch<SettingsResponse>("/api/admin/settings"),
  });
  const templatesQuery = useQuery({
    queryKey: ["quota-templates"],
    queryFn: () => apiFetch<QuotaTemplatesResponse>("/api/admin/quota-templates"),
    staleTime: 5 * 60_000,
  });
  const statusQuery = useQuery({
    queryKey: ["local-ocr-status"],
    queryFn: () => apiFetch<LocalOcrStatus>("/api/admin/local-ocr/status"),
    refetchInterval: (query) =>
      query.state.data?.state === "starting" ? 1000 : false,
  });

  const form = useForm<SettingsValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      cache_enabled: true,
      cache_ttl_seconds: "3600",
      cache_max_entries: "1000",
      request_deadline_ms: "20000",
      default_timeout_ms: "8000",
      local_ocr_enabled: false,
    },
  });

  const editable = settingsQuery.data?.editable;
  const errors = form.formState.errors;
  useEffect(() => {
    if (!editable) return;
    form.reset({
      cache_enabled: editable.cache_enabled,
      cache_ttl_seconds: String(editable.cache_ttl_seconds),
      cache_max_entries: String(editable.cache_max_entries),
      request_deadline_ms: String(editable.request_deadline_ms),
      default_timeout_ms: String(editable.default_timeout_ms),
      local_ocr_enabled: editable.local_ocr_enabled,
    });
  }, [editable, form]);

  const blocker = useUnsavedChanges(form.formState.isDirty);

  const save = useMutation({
    scope: { id: "settings" },
    mutationFn: (values: SettingsValues) => {
      const dirty = form.formState.dirtyFields as Partial<
        Record<keyof SettingsValues, boolean>
      >;
      const payload: Record<string, unknown> = {};
      for (const key of Object.keys(settingsSchema.shape) as Array<
        keyof SettingsValues
      >) {
        if (!dirty[key]) continue;
        if (
          key === "local_ocr_enabled" &&
          statusQuery.data?.installed === false
        ) {
          continue;
        }
        payload[key] =
          key === "local_ocr_enabled" ? values[key] : Number(values[key]);
      }
      return apiFetch<SettingsUpdateResponse>("/api/admin/settings", {
        method: "PUT",
        body: payload,
      });
    },
    onSuccess: (result) => {
      form.reset({
        cache_enabled: result.settings.cache_enabled,
        cache_ttl_seconds: String(result.settings.cache_ttl_seconds),
        cache_max_entries: String(result.settings.cache_max_entries),
        request_deadline_ms: String(result.settings.request_deadline_ms),
        default_timeout_ms: String(result.settings.default_timeout_ms),
        local_ocr_enabled: result.settings.local_ocr_enabled,
      });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["local-ocr-status"] });
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
      toast.success("设置已保存");
      if (result.cache_cleared) {
        toast.info("缓存参数或本地 OCR 开关已变更，缓存已清空");
      }
    },
    onError: (error) => {
      if (error instanceof ApiError && error.fields.length > 0) {
        for (const field of error.fields) {
          if (field.field in settingsSchema.shape) {
            form.setError(field.field as keyof SettingsValues, { message: field.message });
          }
        }
      }
      toast.error(error instanceof Error ? error.message : "保存失败，请重试。");
    },
  });

  const clearCache = useMutation({
    scope: { id: "settings" },
    mutationFn: () => apiFetch<{ cleared: number }>("/api/admin/cache/clear", { method: "POST" }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
      toast.success(`已清空 ${formatNumber(result.cleared)} 条缓存`);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "清空失败。"),
  });

  if (settingsQuery.isPending) {
    return (
      <div className="space-y-4" aria-busy="true">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (settingsQuery.isError || !settingsQuery.data) {
    return (
      <ErrorState
        description={settingsQuery.error instanceof Error ? settingsQuery.error.message : undefined}
        onRetry={() => void settingsQuery.refetch()}
      />
    );
  }

  const readonly = settingsQuery.data.readonly;

  return (
    <div className="max-w-[900px]">
      <PageHeader
        title="设置"
        description="保存后立即生效；缓存参数变更会清空现有缓存。"
        actions={
          <Button onClick={() => clearCache.mutate()} disabled={clearCache.isPending}>
            {clearCache.isPending ? "清空中…" : "清空缓存"}
          </Button>
        }
      />

      <form
        onSubmit={form.handleSubmit((values) => save.mutate(values))}
        noValidate
      >
        <Section id="editable-heading" title="可编辑" level="primary">
          <Panel>
            <div className="flex items-center justify-between gap-6 border-b border-line px-5 py-4">
              <div>
                <p className="text-body text-ink">结果缓存</p>
                <p className="mt-0.5 text-micro text-muted">
                  关闭后不再写入新条目，已缓存结果仍可命中。
                </p>
              </div>
              <Controller
                control={form.control}
                name="cache_enabled"
                render={({ field }) => (
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    aria-label="启用结果缓存"
                  />
                )}
              />
            </div>
            <div className="grid gap-5 px-5 py-4 md:grid-cols-2">
              <div>
                <Label htmlFor="cache_ttl_seconds">缓存 TTL（秒）</Label>
                <Input
                  id="cache_ttl_seconds"
                  className="mt-1.5"
                  {...form.register("cache_ttl_seconds")}
                  aria-invalid={errors.cache_ttl_seconds ? true : undefined}
                  aria-describedby={
                    errors.cache_ttl_seconds ? "cache_ttl_seconds-error" : undefined
                  }
                />
                <FieldError id="cache_ttl_seconds-error">
                  {errors.cache_ttl_seconds?.message}
                </FieldError>
              </div>
              <div>
                <Label htmlFor="cache_max_entries">缓存容量（条）</Label>
                <Input
                  id="cache_max_entries"
                  className="mt-1.5"
                  {...form.register("cache_max_entries")}
                  aria-invalid={errors.cache_max_entries ? true : undefined}
                  aria-describedby={
                    errors.cache_max_entries ? "cache_max_entries-error" : undefined
                  }
                />
                <FieldError id="cache_max_entries-error">
                  {errors.cache_max_entries?.message}
                </FieldError>
              </div>
              <div>
                <Label htmlFor="request_deadline_ms">请求总预算（毫秒）</Label>
                <Input
                  id="request_deadline_ms"
                  className="mt-1.5"
                  {...form.register("request_deadline_ms")}
                  aria-invalid={errors.request_deadline_ms ? true : undefined}
                  aria-describedby={
                    errors.request_deadline_ms ? "request_deadline_ms-error" : undefined
                  }
                />
                <FieldError id="request_deadline_ms-error">
                  {errors.request_deadline_ms?.message}
                </FieldError>
              </div>
              <div>
                <Label htmlFor="default_timeout_ms">账号默认超时（毫秒）</Label>
                <Input
                  id="default_timeout_ms"
                  className="mt-1.5"
                  {...form.register("default_timeout_ms")}
                  aria-invalid={errors.default_timeout_ms ? true : undefined}
                  aria-describedby={
                    errors.default_timeout_ms ? "default_timeout_ms-error" : undefined
                  }
                />
                <FieldError id="default_timeout_ms-error">
                  {errors.default_timeout_ms?.message}
                </FieldError>
              </div>
            </div>
            <div className="border-t border-line px-5 py-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-body text-ink">本地 OCR</p>
                  <p className="mt-0.5 text-micro text-muted">
                    云厂商全部不可用时由本地 RapidOCR 兜底；关闭后 provider=local 返回 403。
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Controller
                    control={form.control}
                    name="local_ocr_enabled"
                    render={({ field }) => (
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                        disabled={statusQuery.data?.installed === false}
                        aria-label="启用本地 OCR"
                      />
                    )}
                  />
                  <FieldError>{errors.local_ocr_enabled?.message}</FieldError>
                </div>
              </div>
              <div className="mt-3">
                {statusQuery.isPending ? (
                  <Skeleton className="h-16 w-full" />
                ) : statusQuery.isError ? (
                  <div className="flex flex-wrap items-center gap-3 text-meta text-muted">
                    <span>本地状态暂不可用。</span>
                    <Button
                      onClick={() => void statusQuery.refetch()}
                      disabled={statusQuery.isFetching}
                    >
                      {statusQuery.isFetching ? "重试中…" : "重试"}
                    </Button>
                  </div>
                ) : statusQuery.data ? (
                  statusQuery.data.installed === false ? (
                    <p className="text-meta text-warn">
                      当前镜像未安装 local extra，请使用内置该依赖的 0.3.0 镜像；此开关已禁用。
                    </p>
                  ) : (
                    <dl className="grid gap-x-8 gap-y-2 text-meta md:grid-cols-2">
                      <div className="flex items-baseline gap-3">
                        <dt className="w-20 shrink-0 text-micro text-muted">状态</dt>
                        <dd>
                          <StatusDot state={statusQuery.data.state} />
                        </dd>
                      </div>
                      <div className="flex items-baseline gap-3">
                        <dt className="w-20 shrink-0 text-micro text-muted">模型</dt>
                        <dd>
                          {statusQuery.data.model.family}{" "}
                          {statusQuery.data.model.variant}（
                          {statusQuery.data.model.engine}）
                        </dd>
                      </div>
                      <div className="flex items-baseline gap-3">
                        <dt className="w-20 shrink-0 text-micro text-muted">最近耗时</dt>
                        <dd className="tabular-nums">
                          {statusQuery.data.last_latency_ms === null
                            ? "—"
                            : `${formatNumber(statusQuery.data.last_latency_ms)} ms`}
                        </dd>
                      </div>
                      <div className="flex items-baseline gap-3">
                        <dt className="w-20 shrink-0 text-micro text-muted">请求 / 兜底</dt>
                        <dd className="tabular-nums">
                          {formatNumber(statusQuery.data.requests_total)} /{" "}
                          {formatNumber(statusQuery.data.fallback_total)}
                        </dd>
                      </div>
                      <div className="flex items-baseline gap-3 md:col-span-2">
                        <dt className="w-20 shrink-0 text-micro text-muted">最近错误</dt>
                        <dd
                          className="min-w-0 truncate text-muted"
                          title={statusQuery.data.last_error ?? undefined}
                        >
                          {statusQuery.data.last_error ?? "无"}
                        </dd>
                      </div>
                    </dl>
                  )
                ) : null}
              </div>
            </div>
            <div className="flex items-center gap-2 border-t border-line px-5 py-3">
              <Button
                type="submit"
                variant="primary"
                disabled={save.isPending || !form.formState.isDirty}
              >
                {save.isPending ? "保存中…" : "保存设置"}
              </Button>
              <Button
                onClick={() => form.reset()}
                disabled={save.isPending || !form.formState.isDirty}
              >
                撤销修改
              </Button>
            </div>
          </Panel>
        </Section>
      </form>

      <Section id="readonly-heading" title="只读">
        <dl className="grid gap-x-12 md:grid-cols-2">
          {[
            ["API 鉴权", readonly.api_auth_enabled ? "已启用" : "已关闭"],
            ["版本", readonly.version],
            ["上传上限", `${formatNumber(Math.round(readonly.max_upload_bytes / 1024 / 1024))} MB`],
            ["最大像素", `${formatNumber(readonly.max_image_pixels)} px`],
            ["并发上限", formatNumber(readonly.max_concurrent_requests)],
            ["会话时长", `${formatNumber(readonly.session_ttl_seconds)} 秒`],
            ["面板产物", readonly.frontend_built ? "已就绪" : "未构建"],
          ].map(([label, value]) => (
            <div
              key={label}
              className="flex items-baseline gap-4 border-t border-line py-2.5"
            >
              <dt className="w-20 shrink-0 text-micro text-muted">{label}</dt>
              <dd className="text-meta tabular-nums text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </Section>

        <Section id="templates-heading" title="配额模板">
          {templatesQuery.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : templatesQuery.isError ? (
            <ErrorState
              description="无法加载配额模板。"
              onRetry={() => void templatesQuery.refetch()}
            />
          ) : (
            <>
              <p className="mb-4 text-micro text-warn">{templatesQuery.data.disclaimer}</p>
              <div className="grid gap-x-12 md:grid-cols-2">
                {templatesQuery.data.providers.map((template) => (
                  <div key={template.code} className="border-t border-line py-3">
                    <p className="text-body text-ink">{template.name}</p>
                    <p className="mt-1 text-meta tabular-nums text-muted">
                      日 {template.reference_quota.daily ?? "不限"}，月{" "}
                      {template.reference_quota.monthly === null
                        ? "不限"
                        : formatNumber(template.reference_quota.monthly)}
                      ，总量 {template.reference_quota.total ?? "不限"}
                    </p>
                    <p className="mt-1 text-micro text-muted">{template.notes}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </Section>

      <LeaveConfirmDialog blocker={blocker} />
    </div>
  );
}
