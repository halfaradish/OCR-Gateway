import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { FilterBar, FilterField } from "@/components/filter-bar";
import { PageHeader } from "@/components/page-header";
import { QuotaRuler } from "@/components/quota-ruler";
import { Panel, PanelToolbar } from "@/components/section";
import { EmptyState, ErrorState } from "@/components/states";
import { StatusDot } from "@/components/status-dot";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { FieldError, Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { ApiError, apiFetch } from "@/lib/api";
import { providerLabel } from "@/lib/providers";
import { formatLatency } from "@/lib/time";
import { LeaveConfirmDialog, useUnsavedChanges } from "@/lib/unsaved-changes";
import { errorMessage } from "@/lib/utils";
import type { Account, Member, ProviderCode, TestAccountResponse } from "@/types";

const PROVIDERS: Array<{ value: ProviderCode; label: string }> = [
  { value: "baidu", label: "百度智能云" },
  { value: "tencent", label: "腾讯云" },
];

const CREDENTIAL_FIELDS: Record<ProviderCode, Array<{ key: string; label: string }>> = {
  baidu: [
    { key: "app_id", label: "AppID" },
    { key: "api_key", label: "API Key" },
    { key: "secret_key", label: "Secret Key" },
  ],
  tencent: [
    { key: "secret_id", label: "SecretId" },
    { key: "secret_key", label: "SecretKey" },
  ],
};

const STATE_FILTERS = [
  { value: "", label: "全部状态" },
  { value: "active", label: "可用" },
  { value: "cooling", label: "冷却中" },
  { value: "invalid", label: "凭证失效" },
  { value: "quota_exhausted", label: "配额耗尽" },
  { value: "disabled", label: "已禁用" },
];

const optionalNonNegative = (message: string) =>
  z
    .string()
    .refine((value) => value === "" || /^\d+$/.test(value), message);

const accountSchema = z.object({
  provider: z.enum(["baidu", "tencent"]),
  name: z.string().trim().min(1, "请填写账号名称。").max(100, "名称最长 100 字。"),
  owner_id: z.string(),
  priority: z.string().regex(/^\d+$/, "优先级必须是整数。"),
  weight: z.string().regex(/^[1-9]\d*$/, "权重至少为 1。"),
  max_concurrency: z.string().regex(/^[1-9]\d*$/, "并发至少为 1。"),
  qps_limit: z.string().refine((value) => value === "" || Number(value) > 0, "QPS 需大于 0。"),
  reset_day: z
    .string()
    .regex(/^\d+$/, "重置日必须是整数。")
    .refine((value) => Number(value) >= 1 && Number(value) <= 28, "重置日需在 1–28。"),
  timeout_ms: z
    .string()
    .refine(
      (value) => value === "" || (/^\d+$/.test(value) && Number(value) > 0),
      "超时需为正整数毫秒。",
    ),
  quota_daily: optionalNonNegative("日配额需为非负整数。"),
  quota_monthly: optionalNonNegative("月配额需为非负整数。"),
  quota_total: optionalNonNegative("总量配额需为非负整数。"),
  credentials: z.record(z.string(), z.string()),
});

type AccountFormValues = z.infer<typeof accountSchema>;

const DEFAULTS: AccountFormValues = {
  provider: "baidu",
  name: "",
  owner_id: "",
  priority: "100",
  weight: "1",
  max_concurrency: "2",
  qps_limit: "5",
  reset_day: "1",
  timeout_ms: "",
  quota_daily: "",
  quota_monthly: "",
  quota_total: "",
  credentials: {},
};

function toNullableNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function credentialsComplete(values: AccountFormValues): boolean {
  return CREDENTIAL_FIELDS[values.provider].every(
    (field) => (values.credentials[field.key] ?? "").trim() !== "",
  );
}

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const providerFilter = params.get("provider") ?? "";
  const stateFilter = params.get("state") ?? "";

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiFetch<Account[]>("/api/admin/accounts"),
  });
  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiFetch<Member[]>("/api/admin/users"),
  });

  const [editing, setEditing] = useState<Account | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirm, setConfirm] = useState<{ kind: "reset" | "delete"; account: Account } | null>(null);
  const [testResult, setTestResult] = useState<TestAccountResponse | null>(null);
  const [testPending, setTestPending] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const form = useForm<AccountFormValues>({
    resolver: zodResolver(accountSchema),
    defaultValues: DEFAULTS,
  });
  const provider = form.watch("provider");
  const credentialsError = errorMessage(form.formState.errors.credentials);
  // Route changes while the dialog holds unsaved edits ask for confirmation first.
  const blocker = useUnsavedChanges(dialogOpen && form.formState.isDirty);
  const rootError = errorMessage(form.formState.errors.root);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["accounts"] });
    void queryClient.invalidateQueries({ queryKey: ["overview"] });
  };

  const saveMutation = useMutation({
    scope: { id: "accounts" },
    mutationFn: async (values: AccountFormValues) => {
      const common = {
        name: values.name.trim(),
        owner_id: values.owner_id === "" ? null : Number(values.owner_id),
        priority: Number(values.priority),
        weight: Number(values.weight),
        max_concurrency: Number(values.max_concurrency),
        qps_limit: toNullableNumber(values.qps_limit),
        quota_daily: toNullableNumber(values.quota_daily),
        quota_monthly: toNullableNumber(values.quota_monthly),
        quota_total: toNullableNumber(values.quota_total),
        reset_day: Number(values.reset_day),
      };
      const credentials = credentialsComplete(values) ? values.credentials : undefined;
      if (editing) {
        const payload: Record<string, unknown> = { ...common };
        if (credentials) payload.credentials = credentials;
        // Omitting `timeout_ms` keeps the stored value; explicit null is rejected by the API.
        if (values.timeout_ms !== "") payload.timeout_ms = Number(values.timeout_ms);
        return apiFetch<Account>(`/api/admin/accounts/${editing.id}`, {
          method: "PATCH",
          body: payload,
        });
      }
      return apiFetch<Account>("/api/admin/accounts", {
        method: "POST",
        body: {
          ...common,
          provider: values.provider,
          enabled: true,
          timeout_ms: values.timeout_ms === "" ? undefined : Number(values.timeout_ms),
          credentials: credentials ?? {},
        },
      });
    },
    onSuccess: () => {
      invalidate();
      setDialogOpen(false);
      toast.success(editing ? "账号已更新" : "账号已创建");
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : "保存失败，请重试。";
      const fields = error instanceof ApiError ? error.fields : [];
      const credentialError = fields.find((field) => field.field.startsWith("credentials"));
      if (credentialError) {
        form.setError("credentials", { message: credentialError.message });
      } else if (fields.length > 0) {
        const first = fields[0];
        if (first) form.setError("root", { message: first.message });
      }
      toast.error(message);
    },
  });

  const toggleMutation = useMutation({
    scope: { id: "accounts" },
    mutationFn: (account: Account) =>
      apiFetch<Account>(`/api/admin/accounts/${account.id}`, {
        method: "PATCH",
        body: { enabled: !account.enabled },
      }),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(error instanceof Error ? error.message : "操作失败。"),
  });

  const resetMutation = useMutation({
    scope: { id: "accounts" },
    mutationFn: (account: Account) =>
      apiFetch<{ state: string }>(`/api/admin/accounts/${account.id}/reset-state`, {
        method: "POST",
      }),
    onSuccess: () => {
      invalidate();
      setConfirm(null);
      toast.success("账号已恢复可用，配额计数已清零");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "操作失败。"),
  });

  const deleteMutation = useMutation({
    scope: { id: "accounts" },
    mutationFn: (account: Account) =>
      apiFetch<void>(`/api/admin/accounts/${account.id}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidate();
      setConfirm(null);
      toast.success("账号已删除");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "删除失败。"),
  });

  const openCreate = () => {
    setEditing(null);
    form.reset(DEFAULTS);
    setDialogOpen(true);
  };

  const openEdit = (account: Account) => {
    setEditing(account);
    form.reset({
      ...DEFAULTS,
      provider: account.provider,
      name: account.name,
      owner_id: account.owner_id ? String(account.owner_id) : "",
      priority: String(account.priority),
      weight: String(account.weight),
      max_concurrency: String(account.max_concurrency),
      qps_limit: account.qps_limit === null ? "" : String(account.qps_limit),
      reset_day: String(account.reset_day),
      timeout_ms: String(account.timeout_ms),
      quota_daily: account.quota_daily === null ? "" : String(account.quota_daily),
      quota_monthly: account.quota_monthly === null ? "" : String(account.quota_monthly),
      quota_total: account.quota_total === null ? "" : String(account.quota_total),
      credentials: {},
    });
    setDialogOpen(true);
  };

  useEffect(() => {
    if (dialogOpen) form.clearErrors();
  }, [dialogOpen, form]);

  const runTest = async (account: Account) => {
    setBusyId(account.id);
    setTestPending(true);
    setTestResult(null);
    try {
      const result = await apiFetch<TestAccountResponse>(
        `/api/admin/accounts/${account.id}/test`,
        { method: "POST", timeoutMs: account.timeout_ms + 5000 },
      );
      setTestResult(result);
    } catch (error) {
      setTestResult({
        ok: false,
        provider: account.provider,
        error_code: error instanceof ApiError ? error.code : "NETWORK_ERROR",
        message: error instanceof Error ? error.message : "测活失败。",
        latency_ms: 0,
      });
    } finally {
      setBusyId(null);
      setTestPending(false);
    }
  };

  const users = usersQuery.data ?? [];
  const filtered = useMemo(() => {
    const rows = accountsQuery.data ?? [];
    return rows.filter((account) => {
      if (providerFilter && account.provider !== providerFilter) return false;
      if (stateFilter && account.state !== stateFilter) return false;
      return true;
    });
  }, [accountsQuery.data, providerFilter, stateFilter]);

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const saving = saveMutation.isPending;
  const rowBusy = busyId !== null || toggleMutation.isPending || deleteMutation.isPending;

  const renderActions = (account: Account) => (
    <>
      <Button size="sm" variant="ghost" disabled={rowBusy} onClick={() => void runTest(account)}>
        测活
      </Button>
      <Button size="sm" variant="ghost" onClick={() => openEdit(account)}>
        <Pencil aria-hidden="true" />
        编辑
      </Button>
      <Button
        size="sm"
        variant="ghost"
        disabled={rowBusy}
        onClick={() => toggleMutation.mutate(account)}
      >
        {account.enabled ? "禁用" : "启用"}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        disabled={rowBusy}
        onClick={() => setConfirm({ kind: "reset", account })}
      >
        重置
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="text-danger"
        disabled={rowBusy}
        onClick={() => setConfirm({ kind: "delete", account })}
      >
        <Trash2 aria-hidden="true" />
        删除
      </Button>
    </>
  );

  return (
    <div>
      <PageHeader
        title="账号"
        meta={
          accountsQuery.data ? (
            <>
              <span>{accountsQuery.data.length} 个账号</span>
              <span>
                {accountsQuery.data.filter((account) => account.state === "active").length} 个可用
              </span>
            </>
          ) : undefined
        }
        description="优先级、并发与配额由网关调度使用，配额为准实时数据。"
        actions={
          <Button variant="primary" onClick={openCreate}>
            <Plus aria-hidden="true" />
            新建账号
          </Button>
        }
      />

      <Panel>
        <PanelToolbar>
          <FilterBar>
            <FilterField htmlFor="provider-filter" label="厂商">
              <Select
                id="provider-filter"
                selectSize="sm"
                value={providerFilter}
                onChange={(event) => updateFilter("provider", event.target.value)}
              >
                <option value="">全部厂商</option>
                {PROVIDERS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </FilterField>
            <FilterField htmlFor="state-filter" label="状态">
              <Select
                id="state-filter"
                selectSize="sm"
                value={stateFilter}
                onChange={(event) => updateFilter("state", event.target.value)}
              >
                {STATE_FILTERS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </FilterField>
          </FilterBar>
          <p className="text-micro tabular-nums text-muted">
            显示 {filtered.length} / {accountsQuery.data?.length ?? 0} 个
          </p>
        </PanelToolbar>

        {accountsQuery.isPending ? (
          <div className="space-y-2 p-5" aria-busy="true">
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
          </div>
        ) : accountsQuery.isError ? (
          <div className="px-5">
            <ErrorState
              description={accountsQuery.error instanceof Error ? accountsQuery.error.message : undefined}
              onRetry={() => void accountsQuery.refetch()}
            />
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-5">
            <EmptyState
              title={accountsQuery.data?.length ? "当前筛选下没有账号。" : "还没有账号"}
              description={
                accountsQuery.data?.length
                  ? "调整筛选条件试试。"
                  : "添加一个百度或腾讯账号后即可开始识别。"
              }
              action={
                accountsQuery.data?.length ? undefined : (
                  <Button variant="primary" onClick={openCreate}>
                    新建账号
                  </Button>
                )
              }
            />
          </div>
        ) : (
          <Table inset className="md:min-w-[1100px]">
            <TableHead>
              <TableRow>
                <TableHeaderCell className="hidden md:table-cell">厂商</TableHeaderCell>
                <TableHeaderCell>名称</TableHeaderCell>
                <TableHeaderCell className="hidden md:table-cell">贡献者</TableHeaderCell>
                <TableHeaderCell className="hidden text-right md:table-cell">优先级</TableHeaderCell>
                <TableHeaderCell className="hidden lg:table-cell">配额</TableHeaderCell>
                <TableHeaderCell>状态</TableHeaderCell>
                <TableHeaderCell className="hidden text-right md:table-cell">EWMA</TableHeaderCell>
                <TableHeaderCell className="hidden xl:table-cell">最近错误</TableHeaderCell>
                <TableHeaderCell className="text-right">操作</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.map((account) => {
                const usage = account.quota_usage;
                const unconfigured =
                  usage.daily.limit === null &&
                  usage.monthly.limit === null &&
                  usage.total.limit === null;
                return (
                  <TableRow key={account.id}>
                    <TableCell className="hidden whitespace-nowrap text-muted md:table-cell">
                      {providerLabel(account.provider)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <span className="block">{account.name}</span>
                      <span className="block text-micro text-muted md:hidden">
                        {providerLabel(account.provider)}
                      </span>
                    </TableCell>
                    <TableCell className="hidden whitespace-nowrap text-muted md:table-cell">
                      {account.owner_id === null ? "—" : (account.owner_name ?? "已删除")}
                    </TableCell>
                    <TableCell className="hidden text-right tabular-nums md:table-cell">
                      {account.priority}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {unconfigured ? (
                        <span className="text-meta text-warn">未配置额度，可能超用</span>
                      ) : (
                        <QuotaRuler
                          label="月"
                          used={usage.monthly.used}
                          limit={usage.monthly.limit}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusDot state={account.state} />
                    </TableCell>
                    <TableCell className="hidden text-right tabular-nums md:table-cell">
                      {formatLatency(Math.round(account.ewma_latency_ms))}
                    </TableCell>
                    <TableCell className="hidden max-w-[180px] text-meta text-muted xl:table-cell">
                      {account.last_error_code ? (
                        <span title={account.last_error_message ?? ""}>
                          {account.last_error_code}
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {/* Narrow screens keep name/state/actions visible; the actions collapse. */}
                      <details className="md:hidden">
                        <summary className="cursor-pointer select-none text-meta text-blue">
                          操作
                        </summary>
                        <div className="mt-2 flex flex-col items-start gap-1">
                          {renderActions(account)}
                        </div>
                      </details>
                      <div className="hidden flex-wrap justify-end gap-1 md:flex">
                        {renderActions(account)}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Panel>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (open) return;
          if (form.formState.isDirty && !saving && !window.confirm("放弃未保存的修改？")) return;
          setDialogOpen(false);
        }}
      >
        <DialogContent wide className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "编辑账号" : "新建账号"}</DialogTitle>
            <DialogDescription>
              {editing
                ? "凭证字段留空表示不修改；超时留空表示保持当前值。"
                : "留空的超时与配额表示使用默认值 / 不限。"}
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
            noValidate
            className="space-y-4"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="provider">厂商</Label>
                <Select
                  id="provider"
                  className="mt-1.5 w-full"
                  disabled={Boolean(editing)}
                  {...form.register("provider")}
                >
                  {PROVIDERS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="name">名称</Label>
                <Input id="name" className="mt-1.5" {...form.register("name")} />
                <FieldError>{form.formState.errors.name?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="owner">贡献者</Label>
                <Select id="owner" className="mt-1.5 w-full" {...form.register("owner_id")}>
                  <option value="">无</option>
                  {users.map((user) => (
                    <option key={user.id} value={String(user.id)}>
                      {user.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="priority">优先级（数字越小越优先）</Label>
                <Input id="priority" className="mt-1.5" {...form.register("priority")} />
                <FieldError>{form.formState.errors.priority?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="weight">权重</Label>
                <Input id="weight" className="mt-1.5" {...form.register("weight")} />
                <FieldError>{form.formState.errors.weight?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="max_concurrency">并发上限</Label>
                <Input
                  id="max_concurrency"
                  className="mt-1.5"
                  {...form.register("max_concurrency")}
                />
                <FieldError>{form.formState.errors.max_concurrency?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="qps_limit">QPS 上限（留空为不限）</Label>
                <Input id="qps_limit" className="mt-1.5" {...form.register("qps_limit")} />
                <FieldError>{form.formState.errors.qps_limit?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="reset_day">月度重置日</Label>
                <Input id="reset_day" className="mt-1.5" {...form.register("reset_day")} />
                <FieldError>{form.formState.errors.reset_day?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="timeout_ms">
                  {editing ? "超时（毫秒，留空保持原值）" : "超时（毫秒，留空用运行时默认）"}
                </Label>
                <Input id="timeout_ms" className="mt-1.5" {...form.register("timeout_ms")} />
                <FieldError>{form.formState.errors.timeout_ms?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="quota_daily">日配额（留空不限）</Label>
                <Input id="quota_daily" className="mt-1.5" {...form.register("quota_daily")} />
                <FieldError>{form.formState.errors.quota_daily?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="quota_monthly">月配额（留空不限）</Label>
                <Input
                  id="quota_monthly"
                  className="mt-1.5"
                  {...form.register("quota_monthly")}
                />
                <FieldError>{form.formState.errors.quota_monthly?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="quota_total">总量配额（留空不限）</Label>
                <Input id="quota_total" className="mt-1.5" {...form.register("quota_total")} />
                <FieldError>{form.formState.errors.quota_total?.message}</FieldError>
              </div>
            </div>

            <fieldset className="border-t border-line pt-4">
              <legend className="text-meta font-medium text-ink">
                {editing ? "凭证（留空不修改）" : "凭证"}
              </legend>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                {CREDENTIAL_FIELDS[provider].map((field) => (
                  <div key={field.key}>
                    <Label htmlFor={`credential-${field.key}`}>{field.label}</Label>
                    <Input
                      id={`credential-${field.key}`}
                      className="mt-1.5"
                      autoComplete="off"
                      {...form.register(`credentials.${field.key}`)}
                    />
                  </div>
                ))}
              </div>
              {credentialsError ? (
                <p className="mt-1 text-micro text-danger">{credentialsError}</p>
              ) : null}
              {rootError ? <p className="mt-1 text-micro text-danger">{rootError}</p> : null}
            </fieldset>

            <DialogFooter>
              <Button onClick={() => setDialogOpen(false)} disabled={saving}>
                取消
              </Button>
              <Button type="submit" variant="primary" disabled={saving}>
                {saving ? "保存中…" : "保存"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={testResult !== null || testPending}
        onOpenChange={(open) => !open && setTestResult(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>测活结果</DialogTitle>
            <DialogDescription>测活不会写入用量事件，也不会消耗配额。</DialogDescription>
          </DialogHeader>
          {testPending ? (
            <div className="space-y-2" aria-busy="true">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-full" />
            </div>
          ) : testResult ? (
            <dl className="space-y-2 text-meta">
              <div className="flex gap-3">
                <dt className="w-20 text-muted">结果</dt>
                <dd className={testResult.ok ? "text-success" : "text-danger"}>
                  {testResult.ok ? "成功" : "失败"}
                </dd>
              </div>
              <div className="flex gap-3">
                <dt className="w-20 text-muted">耗时</dt>
                <dd className="tabular-nums">{formatLatency(testResult.latency_ms)}</dd>
              </div>
              {testResult.ok ? (
                <div className="flex gap-3">
                  <dt className="w-20 shrink-0 text-muted">识别文本</dt>
                  <dd className="whitespace-pre-wrap break-words">{testResult.text ?? "—"}</dd>
                </div>
              ) : (
                <>
                  <div className="flex gap-3">
                    <dt className="w-20 text-muted">错误码</dt>
                    <dd className="font-mono">{testResult.error_code ?? "—"}</dd>
                  </div>
                  <div className="flex gap-3">
                    <dt className="w-20 shrink-0 text-muted">说明</dt>
                    <dd>{testResult.message ?? "—"}</dd>
                  </div>
                </>
              )}
            </dl>
          ) : null}
          <DialogFooter>
            <Button onClick={() => setTestResult(null)} disabled={testPending}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirm?.kind === "reset"}
        title="重置账号状态？"
        description="会把账号恢复为可用，并清零该账号今日、本月与总量配额计数。"
        confirmLabel="重置"
        pending={resetMutation.isPending}
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && resetMutation.mutate(confirm.account)}
      />
      <LeaveConfirmDialog blocker={blocker} />
      <ConfirmDialog
        open={confirm?.kind === "delete"}
        title={`删除账号「${confirm?.account.name ?? ""}」？`}
        description="删除后该账号立即移出调度池，历史用量保留；内存配额计数会一并清理。"
        confirmLabel="删除"
        destructive
        pending={deleteMutation.isPending}
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && deleteMutation.mutate(confirm.account)}
      />
    </div>
  );
}

export { PROVIDERS, CREDENTIAL_FIELDS };
