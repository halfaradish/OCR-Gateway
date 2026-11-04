import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { FilterBar, FilterField } from "@/components/filter-bar";
import { PageHeader } from "@/components/page-header";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { apiFetch } from "@/lib/api";
import { providerLabel } from "@/lib/providers";
import { daysAgoLocalIso, formatDateTime, formatLatency, formatNumber, todayLocalIso } from "@/lib/time";
import type { LogRow, LogsResponse } from "@/types";

const PAGE_SIZE = 50;

export default function LogsPage() {
  const [params, setParams] = useSearchParams();
  const from = params.get("from") ?? daysAgoLocalIso(6);
  const to = params.get("to") ?? todayLocalIso();
  const status = params.get("status") ?? "";
  const provider = params.get("provider") ?? "";
  const errorCode = params.get("error") ?? "";
  const offset = Math.max(0, Number(params.get("offset") ?? "0") || 0);
  const [detail, setDetail] = useState<LogRow | null>(null);

  const update = (patch: Record<string, string | number>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === "" || value === undefined) next.delete(key);
      else next.set(key, String(value));
    }
    setParams(next, { replace: true });
  };

  const query = new URLSearchParams({
    from,
    to,
    limit: String(PAGE_SIZE),
    offset: String(offset),
    ...(status ? { success: status === "success" ? "true" : "false" } : {}),
    ...(provider ? { provider } : {}),
    ...(errorCode ? { error_code: errorCode } : {}),
  }).toString();

  const logsQuery = useQuery({
    queryKey: ["logs", query],
    queryFn: () => apiFetch<LogsResponse>(`/api/admin/logs?${query}`),
    placeholderData: keepPreviousData,
  });

  const data = logsQuery.data;
  const total = data?.total ?? 0;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const clearFilters = () => {
    setParams(new URLSearchParams({ from, to }), { replace: true });
  };

  return (
    <div>
      <PageHeader
        title="日志"
        description="只展示元数据，不包含 OCR 原文；时间按 Asia/Shanghai 显示。"
        actions={
          <Button onClick={clearFilters} disabled={!status && !provider && !errorCode && offset === 0}>
            清除筛选
          </Button>
        }
      />

      <Panel>
        <PanelToolbar>
          <FilterBar>
            <FilterField htmlFor="logs-from" label="开始日期">
              <Input
                id="logs-from"
                type="date"
                inputSize="sm"
                value={from}
                onChange={(event) => update({ from: event.target.value, offset: "" })}
              />
            </FilterField>
            <FilterField htmlFor="logs-to" label="结束日期">
              <Input
                id="logs-to"
                type="date"
                inputSize="sm"
                value={to}
                onChange={(event) => update({ to: event.target.value, offset: "" })}
              />
            </FilterField>
            <FilterField htmlFor="logs-status" label="状态">
              <Select
                id="logs-status"
                selectSize="sm"
                value={status}
                onChange={(event) => update({ status: event.target.value, offset: "" })}
              >
                <option value="">全部</option>
                <option value="success">成功</option>
                <option value="failure">失败</option>
              </Select>
            </FilterField>
            <FilterField htmlFor="logs-provider" label="厂商">
              <Select
                id="logs-provider"
                selectSize="sm"
                value={provider}
                onChange={(event) => update({ provider: event.target.value, offset: "" })}
              >
                <option value="">全部</option>
                <option value="baidu">百度智能云</option>
                <option value="tencent">腾讯云</option>
                <option value="auto">自动路由</option>
              </Select>
            </FilterField>
            <FilterField htmlFor="logs-error" label="错误码">
              <Input
                id="logs-error"
                inputSize="sm"
                placeholder="如 TIMEOUT"
                value={errorCode}
                onChange={(event) => update({ error: event.target.value, offset: "" })}
              />
            </FilterField>
          </FilterBar>
        </PanelToolbar>

        {logsQuery.isError ? (
          <div className="border-b border-line bg-surface px-5 py-2 text-meta text-danger">
            {logsQuery.error instanceof Error ? logsQuery.error.message : "查询失败，已保留上一次结果。"}
          </div>
        ) : null}

        {logsQuery.isPending ? (
          <div className="space-y-2 p-5" aria-busy="true">
            {[0, 1, 2, 3, 4].map((row) => (
              <Skeleton key={row} className="h-11 w-full" />
            ))}
          </div>
        ) : total === 0 ? (
          <div className="px-5">
            <EmptyState title="没有符合条件的记录。" description="放宽时间范围或清除筛选后再试。" />
          </div>
        ) : (
          <>
            <Table inset className="md:min-w-[980px]">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>时间</TableHeaderCell>
                  <TableHeaderCell className="hidden lg:table-cell">request_id</TableHeaderCell>
                  <TableHeaderCell className="hidden md:table-cell">用户</TableHeaderCell>
                  <TableHeaderCell className="hidden md:table-cell">厂商</TableHeaderCell>
                  <TableHeaderCell className="hidden lg:table-cell">账号</TableHeaderCell>
                  <TableHeaderCell className="hidden text-right md:table-cell">耗时</TableHeaderCell>
                  <TableHeaderCell>状态</TableHeaderCell>
                  <TableHeaderCell>错误码</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(data?.rows ?? []).map((row) => (
                  <TableRow
                    key={row.id}
                    className="cursor-pointer"
                    onClick={() => setDetail(row)}
                  >
                    <TableCell className="whitespace-nowrap tabular-nums">
                      {formatDateTime(row.created_at)}
                    </TableCell>
                    <TableCell className="hidden max-w-[220px] truncate font-mono text-micro text-muted lg:table-cell">
                      {row.request_id}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{row.user_name ?? "已删除"}</TableCell>
                    <TableCell className="hidden md:table-cell">{providerLabel(row.provider)}</TableCell>
                    <TableCell className="hidden lg:table-cell">{row.account_name ?? "已删除"}</TableCell>
                    <TableCell className="hidden text-right tabular-nums md:table-cell">
                      {formatLatency(row.latency_ms)}
                    </TableCell>
                    <TableCell>
                      <StatusDot
                        state={row.success ? "active" : "invalid"}
                        label={row.success ? "成功" : "失败"}
                      />
                    </TableCell>
                    <TableCell className="font-mono text-micro">
                      {row.error_code ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3 text-micro text-muted">
              <p className="tabular-nums">
                共 {formatNumber(total)} 条，第 {page} / {pages} 页
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={offset === 0 || logsQuery.isFetching}
                  onClick={() => update({ offset: Math.max(0, offset - PAGE_SIZE) })}
                >
                  上一页
                </Button>
                <Button
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total || logsQuery.isFetching}
                  onClick={() => update({ offset: offset + PAGE_SIZE })}
                >
                  下一页
                </Button>
              </div>
            </div>
          </>
        )}
      </Panel>

      {logsQuery.isError && !data ? (
        <ErrorState
          description="无法加载日志。"
          onRetry={() => void logsQuery.refetch()}
        />
      ) : null}

      <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent wide>
          <DialogHeader>
            <DialogTitle>请求详情</DialogTitle>
            <DialogDescription>日志只包含元数据，OCR 原文不落库。</DialogDescription>
          </DialogHeader>
          {detail ? (
            <dl className="grid gap-x-8 gap-y-2 text-meta md:grid-cols-2">
              {[
                ["时间", formatDateTime(detail.created_at)],
                ["request_id", detail.request_id],
                ["状态", detail.success ? "成功" : "失败"],
                ["错误码", detail.error_code ?? "—"],
                ["厂商", providerLabel(detail.provider)],
                ["账号", detail.account_name ?? "已删除"],
                ["用户", detail.user_name ?? "已删除"],
                ["耗时", formatLatency(detail.latency_ms)],
                ["配额消耗", formatNumber(detail.quota_used)],
                ["缓存命中", detail.cached ? "是" : "否"],
                ["图片指纹", detail.image_hash ?? "—"],
              ].map(([label, value]) => (
                <div key={label} className="flex gap-3">
                  <dt className="w-24 shrink-0 text-muted">{label}</dt>
                  <dd className="break-all">{value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          <DialogFooter>
            <Button onClick={() => setDetail(null)}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
