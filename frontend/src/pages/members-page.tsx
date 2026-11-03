import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FieldError, Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/time";
import type { ApiKeyRow, CreatedApiKey, Member } from "@/types";

const memberSchema = z.object({
  name: z.string().trim().min(1, "请填写成员名称。").max(100, "名称最长 100 字。"),
});

const keySchema = z.object({
  name: z.string().trim().min(1, "请填写 Key 名称。").max(100, "名称最长 100 字。"),
  daily_limit: z.string().regex(/^\d+$/, "日限额需为非负整数。"),
  rpm_limit: z.string().regex(/^\d+$/, "RPM 需为非负整数。"),
  unlimited: z.boolean(),
});

type MemberValues = z.infer<typeof memberSchema>;
type KeyValues = z.infer<typeof keySchema>;

const DEFAULT_KEY: KeyValues = {
  name: "",
  daily_limit: "100",
  rpm_limit: "30",
  unlimited: false,
};

export default function MembersPage() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();

  const membersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiFetch<Member[]>("/api/admin/users"),
  });
  const keysQuery = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => apiFetch<ApiKeyRow[]>("/api/admin/api-keys"),
  });

  const [memberDialog, setMemberDialog] = useState(false);
  const [keyDialog, setKeyDialog] = useState(false);
  const [createdKey, setCreatedKey] = useState<CreatedApiKey | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "member"; member: Member } | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiKeyRow | null>(null);

  const memberForm = useForm<MemberValues>({
    resolver: zodResolver(memberSchema),
    defaultValues: { name: "" },
  });
  const keyForm = useForm<KeyValues>({
    resolver: zodResolver(keySchema),
    defaultValues: DEFAULT_KEY,
  });
  const unlimited = keyForm.watch("unlimited");

  const members = membersQuery.data ?? [];
  const selectedId = Number(params.get("member") ?? "");
  const selected = members.find((member) => member.id === selectedId) ?? members[0] ?? null;

  const keysByMember = useMemo(() => {
    const map = new Map<number, ApiKeyRow[]>();
    for (const key of keysQuery.data ?? []) {
      const bucket = map.get(key.user_id) ?? [];
      bucket.push(key);
      map.set(key.user_id, bucket);
    }
    return map;
  }, [keysQuery.data]);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["users"] });
    void queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    void queryClient.invalidateQueries({ queryKey: ["accounts"] });
    void queryClient.invalidateQueries({ queryKey: ["overview"] });
  };

  const createMember = useMutation({
    scope: { id: "members" },
    mutationFn: (values: MemberValues) =>
      apiFetch<Member>("/api/admin/users", { method: "POST", body: values }),
    onSuccess: (member) => {
      invalidate();
      setMemberDialog(false);
      memberForm.reset({ name: "" });
      setParams({ member: String(member.id) }, { replace: true });
      toast.success("成员已创建");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "创建失败。"),
  });

  const toggleMember = useMutation({
    scope: { id: "members" },
    mutationFn: (member: Member) =>
      apiFetch<Member>(`/api/admin/users/${member.id}`, {
        method: "PATCH",
        body: { enabled: !member.enabled },
      }),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(error instanceof Error ? error.message : "操作失败。"),
  });

  const deleteMember = useMutation({
    scope: { id: "members" },
    mutationFn: (member: Member) =>
      apiFetch<void>(`/api/admin/users/${member.id}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidate();
      setConfirm(null);
      const next = new URLSearchParams(params);
      next.delete("member");
      setParams(next, { replace: true });
      toast.success("成员已删除");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "删除失败。"),
  });

  const createKey = useMutation({
    scope: { id: "keys" },
    mutationFn: (values: KeyValues) =>
      apiFetch<CreatedApiKey>("/api/admin/api-keys", {
        method: "POST",
        body: {
          user_id: selected?.id,
          name: values.name.trim(),
          daily_limit: values.unlimited ? null : Number(values.daily_limit),
          rpm_limit: values.unlimited ? null : Number(values.rpm_limit),
        },
      }),
    onSuccess: (key) => {
      invalidate();
      setKeyDialog(false);
      keyForm.reset(DEFAULT_KEY);
      setCreatedKey(key);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "创建失败。"),
  });

  const toggleKey = useMutation({
    scope: { id: "keys" },
    mutationFn: (key: ApiKeyRow) =>
      apiFetch<ApiKeyRow>(`/api/admin/api-keys/${key.id}`, {
        method: "PATCH",
        body: { enabled: !key.enabled },
      }),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(error instanceof Error ? error.message : "操作失败。"),
  });

  const revokeKey = useMutation({
    scope: { id: "keys" },
    mutationFn: (key: ApiKeyRow) =>
      apiFetch<void>(`/api/admin/api-keys/${key.id}`, { method: "DELETE" }),
    onSuccess: () => {
      invalidate();
      setRevokeTarget(null);
      toast.success("Key 已吊销");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "吊销失败。"),
  });

  const selectMember = (member: Member) => {
    setParams({ member: String(member.id) }, { replace: true });
  };

  const memberKeys = selected ? (keysByMember.get(selected.id) ?? []) : [];
  const loading = membersQuery.isPending || keysQuery.isPending;
  const error = membersQuery.error ?? keysQuery.error;

  const copyKey = async () => {
    if (!createdKey) return;
    try {
      await navigator.clipboard.writeText(createdKey.key);
      toast.success("已复制到剪贴板");
    } catch {
      toast.error("剪贴板不可用，请手动选择文本复制。");
    }
  };

  return (
    <div>
      <PageHeader
        title="成员与 Key"
        description="成员是配额归属对象；每个成员可以拥有多个 API Key。"
        actions={
          <Button variant="primary" onClick={() => setMemberDialog(true)}>
            <Plus aria-hidden="true" />
            新建成员
          </Button>
        }
      />

      {loading ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-full" />
        </div>
      ) : error ? (
        <ErrorState
          description={error instanceof Error ? error.message : undefined}
          onRetry={() => {
            void membersQuery.refetch();
            void keysQuery.refetch();
          }}
        />
      ) : members.length === 0 ? (
        <EmptyState
          title="还没有成员"
          description="创建成员后即可为其签发 API Key。"
          action={
            <Button variant="primary" onClick={() => setMemberDialog(true)}>
              新建成员
            </Button>
          }
        />
      ) : (
        <div className="space-y-10">
          <Table className="md:min-w-[720px]">
            <TableHead>
              <TableRow>
                <TableHeaderCell>名称</TableHeaderCell>
                <TableHeaderCell>启用</TableHeaderCell>
                <TableHeaderCell className="text-right">Key 数</TableHeaderCell>
                <TableHeaderCell className="text-right">操作</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {members.map((member) => (
                <TableRow
                  key={member.id}
                  className={selected?.id === member.id ? "bg-mist/60" : undefined}
                >
                  <TableCell>
                    <button
                      type="button"
                      className="text-left text-body text-ink hover:text-blue"
                      onClick={() => selectMember(member)}
                    >
                      {member.name}
                    </button>
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={member.enabled}
                      aria-label={`启用 ${member.name}`}
                      disabled={toggleMember.isPending}
                      onCheckedChange={() => toggleMember.mutate(member)}
                    />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber((keysByMember.get(member.id) ?? []).length)}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => selectMember(member)}>
                        查看 Key
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-danger"
                        disabled={deleteMember.isPending}
                        onClick={() => setConfirm({ kind: "member", member })}
                      >
                        <Trash2 aria-hidden="true" />
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <section aria-labelledby="keys-heading">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 id="keys-heading" className="text-h2 font-medium text-ink">
                {selected ? `${selected.name} 的 Key` : "Key"}
              </h2>
              <Button
                variant="primary"
                disabled={!selected}
                onClick={() => {
                  keyForm.reset(DEFAULT_KEY);
                  setKeyDialog(true);
                }}
              >
                <Plus aria-hidden="true" />
                创建 Key
              </Button>
            </div>
            {memberKeys.length === 0 ? (
              <EmptyState title="该成员还没有 Key。" description="创建后可立即用于调用公共 API。" />
            ) : (
              <Table className="md:min-w-[860px]">
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>前缀</TableHeaderCell>
                    <TableHeaderCell>名称</TableHeaderCell>
                    <TableHeaderCell className="hidden text-right md:table-cell">日限额</TableHeaderCell>
                    <TableHeaderCell className="hidden text-right md:table-cell">RPM</TableHeaderCell>
                    <TableHeaderCell className="hidden lg:table-cell">最近使用</TableHeaderCell>
                    <TableHeaderCell>启用</TableHeaderCell>
                    <TableHeaderCell className="text-right">操作</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {memberKeys.map((key) => (
                    <TableRow key={key.id}>
                      <TableCell className="font-mono text-meta">{key.key_prefix}…</TableCell>
                      <TableCell>{key.name}</TableCell>
                      <TableCell className="hidden text-right tabular-nums md:table-cell">
                        {key.daily_limit === null ? "不限" : formatNumber(key.daily_limit)}
                      </TableCell>
                      <TableCell className="hidden text-right tabular-nums md:table-cell">
                        {key.rpm_limit === null ? "不限" : formatNumber(key.rpm_limit)}
                      </TableCell>
                      <TableCell className="hidden whitespace-nowrap text-muted lg:table-cell">
                        {formatDateTime(key.last_used_at)}
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={key.enabled}
                          aria-label={`启用 ${key.name}`}
                          disabled={toggleKey.isPending}
                          onCheckedChange={() => toggleKey.mutate(key)}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-danger"
                            disabled={revokeKey.isPending}
                            onClick={() => setRevokeTarget(key)}
                          >
                            吊销
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </section>
        </div>
      )}

      <Dialog open={memberDialog} onOpenChange={setMemberDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建成员</DialogTitle>
            <DialogDescription>成员名称用于配额归属与 Key 归属，创建后可停用。</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={memberForm.handleSubmit((values) => createMember.mutate(values))}
            noValidate
            className="space-y-4"
          >
            <div>
              <Label htmlFor="member-name">名称</Label>
              <Input id="member-name" className="mt-1.5" {...memberForm.register("name")} />
              <FieldError>{memberForm.formState.errors.name?.message}</FieldError>
            </div>
            <DialogFooter>
              <Button onClick={() => setMemberDialog(false)} disabled={createMember.isPending}>
                取消
              </Button>
              <Button type="submit" variant="primary" disabled={createMember.isPending}>
                {createMember.isPending ? "创建中…" : "创建"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={keyDialog} onOpenChange={setKeyDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建 Key</DialogTitle>
            <DialogDescription>
              明文只在创建成功时显示一次，关闭后无法再次查看。
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={keyForm.handleSubmit((values) => createKey.mutate(values))}
            noValidate
            className="space-y-4"
          >
            <div>
              <Label htmlFor="key-name">名称</Label>
              <Input id="key-name" className="mt-1.5" {...keyForm.register("name")} />
              <FieldError>{keyForm.formState.errors.name?.message}</FieldError>
            </div>
            <div className="flex items-center gap-2">
              <Controller
                control={keyForm.control}
                name="unlimited"
                render={({ field }) => (
                  <Switch
                    id="key-unlimited"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
              <Label htmlFor="key-unlimited">不限日限额与 RPM</Label>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="key-daily">日限额</Label>
                <Input
                  id="key-daily"
                  className="mt-1.5"
                  disabled={unlimited}
                  {...keyForm.register("daily_limit")}
                />
                <FieldError>{keyForm.formState.errors.daily_limit?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="key-rpm">RPM</Label>
                <Input
                  id="key-rpm"
                  className="mt-1.5"
                  disabled={unlimited}
                  {...keyForm.register("rpm_limit")}
                />
                <FieldError>{keyForm.formState.errors.rpm_limit?.message}</FieldError>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => setKeyDialog(false)} disabled={createKey.isPending}>
                取消
              </Button>
              <Button type="submit" variant="primary" disabled={createKey.isPending}>
                {createKey.isPending ? "创建中…" : "创建"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={createdKey !== null} onOpenChange={(open) => !open && setCreatedKey(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Key 已创建</DialogTitle>
            <DialogDescription>
              这是唯一一次显示明文；关闭后只能看到前缀，无法再次查看。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-sm border border-line bg-paper p-3">
            <code className="select-all break-all font-mono text-meta">{createdKey?.key}</code>
          </div>
          <DialogFooter>
            <Button onClick={() => void copyKey()}>
              <Copy aria-hidden="true" />
              复制
            </Button>
            <Button variant="primary" onClick={() => setCreatedKey(null)}>
              我已保存，关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirm?.kind === "member"}
        title={`删除成员「${confirm?.member.name ?? ""}」？`}
        description={`该成员名下的 ${confirm ? (keysByMember.get(confirm.member.id) ?? []).length : 0} 个 Key 会一并吊销，且无法恢复。`}
        confirmLabel="删除成员"
        destructive
        pending={deleteMember.isPending}
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && deleteMember.mutate(confirm.member)}
      />

      <ConfirmDialog
        open={revokeTarget !== null}
        title={`吊销 Key「${revokeTarget?.name ?? ""}」？`}
        description="吊销后立即失效，无法恢复。如只是临时停用，请改用开关。"
        confirmLabel="吊销"
        destructive
        pending={revokeKey.isPending}
        onCancel={() => setRevokeTarget(null)}
        onConfirm={() => revokeTarget && revokeKey.mutate(revokeTarget)}
      />

    </div>
  );
}
