import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link } from "react-router-dom";

import { QuotaRuler } from "@/components/quota-ruler";
import { EmptyState, ErrorState } from "@/components/states";
import { StatusDot } from "@/components/status-dot";
import { MetricStrip } from "@/components/metric-strip";
import { PageHeader } from "@/components/page-header";
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
import { chartColors } from "@/lib/palette";
import { formatDate, formatDateTime, formatLatency, formatNumber, formatPercent } from "@/lib/time";
import type { AccountQuotaRow, Overview } from "@/types";

function OverviewSkeleton() {
  return (
    <div className="space-y-8" aria-busy="true">
      <Skeleton className="h-9 w-40" />
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <Skeleton key={item} className="h-16" />
        ))}
      </div>
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-[220px] w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

function AccountsQuota({ accounts }: { accounts: AccountQuotaRow[] }) {
  if (accounts.length === 0) {
    return <EmptyState title="还没有账号" description="先在账号页添加一个百度或腾讯账号。" />;
  }
  return (
    <ul className="divide-y divide-line">
      {accounts.map((account) => {
        const usage = account.quota_usage;
        const unconfigured =
          usage.daily.limit === null &&
          usage.monthly.limit === null &&
          usage.total.limit === null;
        return (
          <li key={account.id} className="py-4">
            <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-2">
              <div className="min-w-[180px]">
                <p className="text-body text-ink">{account.name}</p>
                <p className="text-micro text-muted">{account.provider}</p>
              </div>
              <StatusDot state={account.state} />
              {unconfigured ? (
                <p className="text-meta text-warn">未配置额度，可能超用</p>
              ) : (
                <QuotaRuler
                  label="月配额"
                  used={usage.monthly.used}
                  limit={usage.monthly.limit}
                />
              )}
            </div>
            {unconfigured ? null : (
              <details className="mt-2 text-meta text-muted">
                <summary className="cursor-pointer select-none">日配额与总量</summary>
                <div className="mt-2 flex flex-wrap gap-x-10 gap-y-2">
                  <QuotaRuler label="日配额" used={usage.daily.used} limit={usage.daily.limit} />
                  <QuotaRuler label="总量" used={usage.total.used} limit={usage.total.limit} />
                </div>
              </details>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function OverviewPage() {
  const query = useQuery({
    queryKey: ["overview"],
    queryFn: () => apiFetch<Overview>("/api/admin/overview"),
  });

  if (query.isPending) return <OverviewSkeleton />;
  if (query.isError || !query.data) {
    return (
      <ErrorState
        title="数据未加载"
        description={query.error instanceof Error ? query.error.message : "请重试。"}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  const today = data.today;
  const hasRequests = data.series.some((row) => row.requests > 0);

  return (
    <div>
      <PageHeader
        title="总览"
        description={`今日窗口按 Asia/Shanghai 对齐 · 生成于 ${formatDateTime(data.generated_at)}`}
        actions={
          <button
            type="button"
            onClick={() => void query.refetch()}
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-meta text-ink hover:bg-mist"
          >
            刷新
          </button>
        }
      />

      <MetricStrip
        items={[
          { label: "今日请求", value: formatNumber(today.requests), hint: `配额消耗 ${formatNumber(today.quota_used)}` },
          { label: "成功率", value: formatPercent(today.success_rate), hint: `失败 ${formatNumber(today.failure)}` },
          { label: "缓存命中", value: formatPercent(today.cache_hit_rate), hint: `命中 ${formatNumber(today.cached)}` },
          {
            label: "平均延迟",
            value: formatLatency(today.avg_latency_ms),
            hint: today.auto_failures > 0 ? `自动路由失败 ${today.auto_failures} 次` : "含失败请求的真实耗时",
            tone: today.auto_failures > 0 ? "danger" : "default",
          },
        ]}
      />

      <section className="mt-10" aria-labelledby="providers-heading">
        <h2 id="providers-heading" className="mb-3 text-h2 font-medium text-ink">
          厂商
        </h2>
        <div className="grid gap-x-10 gap-y-4 md:grid-cols-2">
          {data.providers.map((provider) => (
            <div key={provider.code} className="border-t border-line pt-3">
              <div className="flex items-baseline justify-between">
                <p className="text-body text-ink">{provider.name}</p>
                <p className="text-micro text-muted">
                  账号 {provider.accounts} · 可用 {provider.available_accounts}
                </p>
              </div>
              <p className="mt-1 text-meta text-muted tabular-nums">
                今日请求 {formatNumber(provider.today_requests)} · 失败{" "}
                <span className={provider.today_failures > 0 ? "text-danger" : undefined}>
                  {formatNumber(provider.today_failures)}
                </span>
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-10" aria-labelledby="series-heading">
        <h2 id="series-heading" className="mb-3 text-h2 font-medium text-ink">
          近 7 日请求
        </h2>
        <div className="relative h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.series} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid stroke={chartColors.line} strokeDasharray="2 4" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={(value: string) => formatDate(value).slice(5)}
                tick={{ fill: chartColors.muted, fontSize: 12 }}
                axisLine={{ stroke: chartColors.line }}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: chartColors.muted, fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={48}
              />
              <Tooltip
                labelFormatter={(value) => formatDate(String(value))}
                formatter={(value) => [formatNumber(Number(value ?? 0)), "请求"]}
                contentStyle={{
                  border: `1px solid ${chartColors.line}`,
                  borderRadius: 4,
                  fontSize: 13,
                }}
              />
              <Line
                type="monotone"
                dataKey="requests"
                stroke={chartColors.navy}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
                activeDot={{ r: 3, fill: chartColors.blue }}
              />
            </LineChart>
          </ResponsiveContainer>
          {hasRequests ? null : (
            <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-meta text-muted">
              所选时间内没有请求。
            </p>
          )}
        </div>
      </section>

      <section className="mt-10" aria-labelledby="quota-heading">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="quota-heading" className="text-h2 font-medium text-ink">
            账号配额
          </h2>
          <Link to="/accounts" className="text-meta text-blue hover:underline">
            管理账号
          </Link>
        </div>
        <AccountsQuota accounts={data.accounts} />
      </section>

      <section className="mt-10" aria-labelledby="errors-heading">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="errors-heading" className="text-h2 font-medium text-ink">
            最近错误
          </h2>
          <Link to="/logs" className="text-meta text-blue hover:underline">
            查看全部日志
          </Link>
        </div>
        {data.recent_errors.length === 0 ? (
          <EmptyState title="最近没有失败请求。" />
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>时间</TableHeaderCell>
                <TableHeaderCell>厂商</TableHeaderCell>
                <TableHeaderCell>账号</TableHeaderCell>
                <TableHeaderCell>错误码</TableHeaderCell>
                <TableHeaderCell className="text-right">耗时</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.recent_errors.map((error) => (
                <TableRow key={error.id}>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {formatDateTime(error.created_at)}
                  </TableCell>
                  <TableCell>{error.provider}</TableCell>
                  <TableCell>{error.account_name ?? "已删除"}</TableCell>
                  <TableCell className="font-mono text-meta">{error.error_code ?? "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatLatency(error.latency_ms)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <footer className="mt-10 border-t border-line pt-4 text-micro text-muted">
        缓存 {data.cache.enabled ? "开启" : "关闭"} · {formatNumber(data.cache.entries)} 条 · TTL{" "}
        {data.cache.ttl_seconds}s · 上限 {formatNumber(data.cache.max_entries)} 条
      </footer>
    </div>
  );
}
