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

import { FilterBar, FilterField } from "@/components/filter-bar";
import { PageHeader } from "@/components/page-header";
import { Panel, Section } from "@/components/section";
import { Segmented } from "@/components/segmented";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
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
        meta={
          summaryQuery.data ? <span>{summaryQuery.data.rows.length} 行汇总</span> : undefined
        }
        actions={
          <Button onClick={exportCsv} disabled={(summaryQuery.data?.rows.length ?? 0) === 0}>
            <Download aria-hidden="true" />
            导出 CSV
          </Button>
        }
      />

      <div className="mb-8 border-y border-line py-3">
        <FilterBar>
            <FilterField htmlFor="usage-from" label="开始日期">
              <Input
                id="usage-from"
                type="date"
                inputSize="sm"
                value={from}
                onChange={(event) => update({ from: event.target.value })}
              />
            </FilterField>
            <FilterField htmlFor="usage-to" label="结束日期">
              <Input
                id="usage-to"
                type="date"
                inputSize="sm"
                value={to}
                onChange={(event) => update({ to: event.target.value })}
              />
            </FilterField>
            <FilterField htmlFor="usage-user" label="成员">
              <Select
                id="usage-user"
                selectSize="sm"
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
            </FilterField>
            <FilterField htmlFor="usage-provider" label="厂商">
              <Select
                id="usage-provider"
                selectSize="sm"
                value={provider}
                onChange={(event) => update({ provider: event.target.value })}
              >
                <option value="">全部厂商</option>
                <option value="baidu">百度智能云</option>
                <option value="tencent">腾讯云</option>
                <option value="auto">自动路由</option>
                <option value="local">本地 RapidOCR</option>
              </Select>
            </FilterField>
            <FilterField htmlFor="usage-account" label="账号">
              <Select
                id="usage-account"
                selectSize="sm"
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
            </FilterField>
          </FilterBar>
      </div>

      {error ? (
        <div className="mb-4 rounded-sm border border-danger/30 bg-surface px-3 py-2 text-meta text-danger">
          时间范围无效或查询失败，已保留上一次结果。
        </div>
      ) : null}

      <Section
        id="usage-chart-heading"
        title="趋势"
        level="primary"
        action={
          <Segmented
            label="指标"
            value={activeMetric.value}
            options={METRICS.map((item) => ({ value: item.value, label: item.label }))}
            onChange={(value) => update({ metric: value })}
          />
        }
      >
        <Panel>
          <div className="relative h-[260px] px-4 py-5">
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
                      allowDecimals={activeMetric.value !== "requests"}
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
        </Panel>
      </Section>

      <Section
        id="usage-table-heading"
        title="汇总"
        meta={`${summaryQuery.data?.rows.length ?? 0} 行`}
        action={
          <Segmented
            label="分组"
            value={group}
            options={GROUPS}
            onChange={(value) => update({ group: value })}
          />
        }
      >
        {summaryQuery.isPending ? (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : (summaryQuery.data?.rows.length ?? 0) === 0 ? (
          <EmptyState title="所选时间内没有请求。" description="放宽时间范围或清除筛选后再试。" />
        ) : (
          <Table className="md:min-w-[820px]">
            <TableHead>
              <TableRow>
                <TableHeaderCell>维度</TableHeaderCell>
                <TableHeaderCell className="text-right">请求</TableHeaderCell>
                <TableHeaderCell className="hidden text-right md:table-cell">成功</TableHeaderCell>
                <TableHeaderCell className="hidden text-right md:table-cell">失败</TableHeaderCell>
                <TableHeaderCell className="hidden text-right lg:table-cell">缓存命中</TableHeaderCell>
                <TableHeaderCell className="hidden text-right lg:table-cell">配额消耗</TableHeaderCell>
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
                  <TableCell className="hidden text-right tabular-nums md:table-cell">
                    {formatNumber(row.success)}
                  </TableCell>
                  <TableCell className="hidden text-right tabular-nums md:table-cell">
                    {formatNumber(row.failure)}
                  </TableCell>
                  <TableCell className="hidden text-right tabular-nums lg:table-cell">
                    {formatNumber(row.cached)}
                  </TableCell>
                  <TableCell className="hidden text-right tabular-nums lg:table-cell">
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
      </Section>

      {seriesQuery.isError && !seriesQuery.data ? (
        <ErrorState
          description="无法加载用量趋势。"
          onRetry={() => void seriesQuery.refetch()}
        />
      ) : null}
    </div>
  );
}
