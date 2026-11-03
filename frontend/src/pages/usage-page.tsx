import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useSearchParams } from "react-router-dom";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { downloadCsv } from "@/lib/csv";
import { chartColors } from "@/lib/palette";
import { daysAgoLocalIso, formatDate, formatLatency, formatNumber, todayLocalIso } from "@/lib/time";
import type { Account, GroupBy, Member, SeriesResponse, SummaryResponse, UsageMetric } from "@/types";

const METRICS: Array<{ value: UsageMetric; label: string; unit: string }> = [
  { value: "requests", label: "请求数", unit: "请求" },
  { value: "success_rate", label: "成功率", unit: "%" },
  { value: "avg_latency", label: "平均延迟", unit: "ms" },
];

const GROUPS: Array<{ value: GroupBy; label: string }> = [
  { value: "provider", label: "按厂商" },
  { value: "user", label: "按成员" },
  { value: "account", label: "按账号" },
];

function seriesValue(row: SeriesResponse["rows"][number], metric: UsageMetric): number | null {
  if (metric === "requests") return row.requests;
  if (metric === "success_rate") {
    return row.requests ? Math.round((row.success / row.requests) * 1000) / 10 : null;
  }
  return row.avg_latency_ms;
}

export default function UsagePage() {
  const [params, setParams] = useSearchParams();
  const from = params.get("from") ?? daysAgoLocalIso(6);
  const to = params.get("to") ?? todayLocalIso();
  const userId = params.get("user") ?? "";
  const provider = params.get("provider") ?? "";
  const accountId = params.get("account") ?? "";
  const metric = (params.get("metric") as UsageMetric | null) ?? "requests";
  const group = (params.get("group") as GroupBy | null) ?? "provider";

  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  };

  const filters = {
    from,
    to,
    ...(userId ? { user_id: userId } : {}),
    ...(provider ? { provider } : {}),
    ...(accountId ? { account_id: accountId } : {}),
  };
  const queryString = new URLSearchParams(filters).toString();

  const seriesQuery = useQuery({
    queryKey: ["usage-series", queryString],
    queryFn: () => apiFetch<SeriesResponse>(`/api/admin/usage/series?${queryString}`),
    placeholderData: keepPreviousData,
  });
  const summaryQuery = useQuery({
    queryKey: ["usage-summary", queryString, group],
    queryFn: () =>
      apiFetch<SummaryResponse>(
        `/api/admin/usage/summary?${queryString}&group_by=${group}`,
      ),
    placeholderData: keepPreviousData,
  });
  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiFetch<Member[]>("/api/admin/users"),
    staleTime: 60_000,
  });
  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiFetch<Account[]>("/api/admin/accounts"),
    staleTime: 60_000,
  });

  const activeMetric =
    METRICS.find((item) => item.value === metric) ??
    ({ value: "requests", label: "请求数", unit: "请求" } as const);
  const chartData = (seriesQuery.data?.rows ?? []).map((row) => ({
    date: row.date,
    value: seriesValue(row, metric),
  }));
  const hasData = chartData.some((point) => (point.value ?? 0) > 0);
  const error = seriesQuery.error ?? summaryQuery.error;

  const exportCsv = () => {
    const rows = summaryQuery.data?.rows ?? [];
    downloadCsv(
      `usage-${from}-${to}.csv`,
      ["维度", "请求", "成功", "失败", "缓存命中", "配额消耗", "平均延迟(ms)"],
      rows.map((row) => [
        row.label ?? "已删除",
        String(row.requests),
        String(row.success),
        String(row.failure),
        String(row.cached),
        String(row.quota_used),
        row.avg_latency_ms === null ? "" : String(row.avg_latency_ms),
      ]),
    );
  };

  return (
    <div>
      <PageHeader
        title="用量"
        description="筛选条件保存在地址栏，刷新或分享链接都会保持当前视图。"
        actions={
          <Button onClick={exportCsv} disabled={(summaryQuery.data?.rows.length ?? 0) === 0}>
            <Download aria-hidden="true" />
            导出 CSV
          </Button>
        }
      />

      <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <div>
          <Label htmlFor="usage-from">开始日期</Label>
          <Input
            id="usage-from"
            type="date"
            className="mt-1.5"
            value={from}
            onChange={(event) => update({ from: event.target.value })}
          />
        </div>
        <div>
          <Label htmlFor="usage-to">结束日期</Label>
          <Input
            id="usage-to"
            type="date"
            className="mt-1.5"
            value={to}
            onChange={(event) => update({ to: event.target.value })}
          />
        </div>
        <div>
          <Label htmlFor="usage-user">成员</Label>
          <Select
            id="usage-user"
            className="mt-1.5 w-full"
            value={userId}
            disabled={usersQuery.isError}
            onChange={(event) => update({ user: event.target.value })}
          >
            <option value="">全部成员</option>
            {(usersQuery.data ?? []).map((user) => (
              <option key={user.id} value={String(user.id)}>
                {user.name}
              </option>
            ))}
          </Select>
          {usersQuery.isError ? (
            <p className="mt-1 text-micro text-danger">成员列表加载失败</p>
          ) : null}
        </div>
        <div>
          <Label htmlFor="usage-provider">厂商</Label>
          <Select
            id="usage-provider"
            className="mt-1.5 w-full"
            value={provider}
            onChange={(event) => update({ provider: event.target.value })}
          >
            <option value="">全部厂商</option>
            <option value="baidu">百度智能云</option>
            <option value="tencent">腾讯云</option>
            <option value="auto">自动路由</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="usage-account">账号</Label>
          <Select
            id="usage-account"
            className="mt-1.5 w-full"
            value={accountId}
            disabled={accountsQuery.isError}
            onChange={(event) => update({ account: event.target.value })}
          >
            <option value="">全部账号</option>
            {(accountsQuery.data ?? []).map((account) => (
              <option key={account.id} value={String(account.id)}>
                {account.name}
              </option>
            ))}
          </Select>
          {accountsQuery.isError ? (
            <p className="mt-1 text-micro text-danger">账号列表加载失败</p>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="mb-4 rounded-sm border border-danger/40 bg-surface px-3 py-2 text-meta text-danger">
          时间范围无效或查询失败，已保留上一次结果。
        </div>
      ) : null}

      <section aria-labelledby="usage-chart-heading">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="usage-chart-heading" className="text-h2 font-medium text-ink">
            趋势
          </h2>
          <div className="flex gap-1" role="group" aria-label="指标">
            {METRICS.map((item) => (
              <Button
                key={item.value}
                size="sm"
                variant={metric === item.value ? "primary" : "ghost"}
                onClick={() => update({ metric: item.value })}
              >
                {item.label}
              </Button>
            ))}
          </div>
        </div>
        <div className="relative h-[240px]">
          {seriesQuery.isPending ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={chartData}
                  margin={{ top: 8, right: 8, bottom: 0, left: -12 }}
                >
                  <CartesianGrid stroke={chartColors.line} strokeDasharray="2 4" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value: string) => formatDate(value).slice(5)}
                    tick={{ fill: chartColors.muted, fontSize: 12 }}
                    axisLine={{ stroke: chartColors.line }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals
                    tick={{ fill: chartColors.muted, fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    width={48}
                  />
                  <Tooltip
                    labelFormatter={(value) => formatDate(String(value))}
                    formatter={(value) => [
                      `${formatNumber(Number(value ?? 0))}${activeMetric.unit === "%" ? "%" : ` ${activeMetric.unit}`}`,
                      activeMetric.label,
                    ]}
                    contentStyle={{
                      border: `1px solid ${chartColors.line}`,
                      borderRadius: 4,
                      fontSize: 13,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={chartColors.navy}
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                    connectNulls={false}
                    activeDot={{ r: 3, fill: chartColors.blue }}
                  />
                </LineChart>
              </ResponsiveContainer>
              {hasData ? null : (
                <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-meta text-muted">
                  所选时间内没有请求。
                </p>
              )}
            </>
          )}
        </div>
      </section>

      <section className="mt-10" aria-labelledby="usage-table-heading">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="usage-table-heading" className="text-h2 font-medium text-ink">
            汇总
          </h2>
          <div className="flex gap-1" role="group" aria-label="分组">
            {GROUPS.map((item) => (
              <Button
                key={item.value}
                size="sm"
                variant={group === item.value ? "primary" : "ghost"}
                onClick={() => update({ group: item.value })}
              >
                {item.label}
              </Button>
            ))}
          </div>
        </div>
        {summaryQuery.isPending ? (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : (summaryQuery.data?.rows.length ?? 0) === 0 ? (
          <EmptyState title="所选时间内没有请求。" description="放宽时间范围或清除筛选后再试。" />
        ) : (
          <Table className="min-w-[820px]">
            <TableHead>
              <TableRow>
                <TableHeaderCell>维度</TableHeaderCell>
                <TableHeaderCell className="text-right">请求</TableHeaderCell>
                <TableHeaderCell className="text-right">成功</TableHeaderCell>
                <TableHeaderCell className="text-right">失败</TableHeaderCell>
                <TableHeaderCell className="text-right">缓存命中</TableHeaderCell>
                <TableHeaderCell className="text-right">配额消耗</TableHeaderCell>
                <TableHeaderCell className="text-right">平均延迟</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(summaryQuery.data?.rows ?? []).map((row) => (
                <TableRow key={String(row.key)}>
                  <TableCell>{row.label ?? "已删除"}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.requests)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.success)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.failure)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.cached)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.quota_used)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatLatency(row.avg_latency_ms)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      {seriesQuery.isError && !seriesQuery.data ? (
        <ErrorState
          description="无法加载用量趋势。"
          onRetry={() => void seriesQuery.refetch()}
        />
      ) : null}
    </div>
  );
}
