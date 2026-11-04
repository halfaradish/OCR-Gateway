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
import { Section, Panel } from "@/components/section";
import { EmptyState, ErrorState } from "@/components/states";
import { StatusDot } from "@/components/status-dot";
import { WatchBand } from "@/components/watch-band";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
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
import { providerLabel } from "@/lib/providers";
import {
  formatDate,
  formatDateTime,
  formatLatency,
  formatNumber,
  formatPercent,
  todayLocalIso,
} from "@/lib/time";
import type { AccountQuotaRow, Overview } from "@/types";
import { cn } from "@/lib/utils";

function OverviewSkeleton() {
  return (
    <div className="space-y-10" aria-busy="true">
      <div className="space-y-3">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-4 w-64" />
      </div>
      <Skeleton className="h-[168px] w-full" />
      <div className="space-y-4">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-32 w-full" />
      </div>
      <Skeleton className="h-[200px] w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

function AccountsQuota({ accounts }: { accounts: AccountQuotaRow[] }) {
  if (accounts.length === 0) {
    return (
      <div className="px-5">
        <EmptyState
          title="还没有账号"
          description="先在账号页添加一个百度或腾讯账号。"
        />
      </div>
    );
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
          <li key={account.id} className="px-5 py-4">
            <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
              <div className="w-[180px] shrink-0">
                <p className="text-body text-ink">{account.name}</p>
                <p className="mt-0.5 text-micro text-muted">{providerLabel(account.provider)}</p>
              </div>
              <StatusDot state={account.state} />
              <div className="ml-auto w-full flex-1 md:w-auto md:max-w-[420px]">
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
            </div>
            {unconfigured ? null : (
              <details className="mt-3 text-micro text-muted md:ml-[212px]">
                <summary className="cursor-pointer select-none hover:text-ink">
                  日配额与总量
                </summary>
                <div className="mt-3 flex flex-wrap gap-x-12 gap-y-3">
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
  const weekTotal = data.series.reduce((sum, row) => sum + row.requests, 0);

  // Yesterday is the series row before today's local date; absent when today is not in the window.
  const todayKey = todayLocalIso();
  const todayIndex = data.series.findIndex((row) => row.date === todayKey);
  const yesterday = todayIndex > 0 ? data.series[todayIndex - 1] : undefined;
  const dayDelta =
    today.requests > 0 && yesterday && yesterday.requests > 0
      ? Math.round(((today.requests - yesterday.requests) / yesterday.requests) * 100)
      : null;

  return (
    <div>
      <PageHeader
        title="总览"
        meta={
          <>
            <span>今日窗口按 Asia/Shanghai 对齐</span>
            <span>生成于 {formatDateTime(data.generated_at)}</span>
          </>
        }
        actions={
          <Button size="sm" onClick={() => void query.refetch()}>
            刷新
          </Button>
        }
      />

      <WatchBand
        lead={{
          label: "今日请求",
          value: formatNumber(today.requests),
          hint: (
            <>
              配额消耗 {formatNumber(today.quota_used)}
              {dayDelta === null ? null : (
                <span className={cn("ml-2", dayDelta >= 0 ? "text-success" : "text-danger")}>
                  较昨日 {dayDelta >= 0 ? "+" : ""}
                  {dayDelta}%
                </span>
              )}
            </>
          ),
        }}
        items={[
          {
            label: "成功率",
            value: formatPercent(today.success_rate),
            hint: `失败 ${formatNumber(today.failure)} 次`,
          },
          {
            label: "缓存命中",
            value: formatPercent(today.cache_hit_rate),
            hint: `命中 ${formatNumber(today.cached)} 次`,
          },
          {
            label: "平均延迟",
            value: formatLatency(today.avg_latency_ms),
            hint:
              today.auto_failures > 0 ? (
                <span className="text-danger">自动路由失败 {today.auto_failures} 次</span>
              ) : undefined,
          },
        ]}
      />

      <Section
        id="quota-heading"
        title="账号配额"
        level="primary"
        meta={`${data.accounts.length} 个账号`}
        action={
          <Link to="/accounts" className="text-meta text-blue hover:underline">
            管理账号
          </Link>
        }
      >
        <Panel>
          <AccountsQuota accounts={data.accounts} />
        </Panel>
      </Section>

      <Section
        id="errors-heading"
        title="最近错误"
        meta={data.recent_errors.length > 0 ? `${data.recent_errors.length} 条` : undefined}
        action={
          <Link to="/logs" className="text-meta text-blue hover:underline">
            查看全部日志
          </Link>
        }
      >
        {data.recent_errors.length === 0 ? (
          <div className="flex items-center gap-2 border-t border-line py-4 text-meta text-muted">
            <span className="size-1.5 rounded-full bg-success" aria-hidden="true" />
            最近没有失败请求
          </div>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>时间</TableHeaderCell>
                <TableHeaderCell className="hidden md:table-cell">厂商</TableHeaderCell>
                <TableHeaderCell className="hidden md:table-cell">账号</TableHeaderCell>
                <TableHeaderCell>错误码</TableHeaderCell>
                <TableHeaderCell className="hidden text-right md:table-cell">耗时</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.recent_errors.map((error) => (
                <TableRow key={error.id}>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {formatDateTime(error.created_at)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {providerLabel(error.provider)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {error.account_name ?? "已删除"}
                  </TableCell>
                  <TableCell
                    className="max-w-[160px] truncate font-mono text-micro"
                    title={error.error_code ?? undefined}
                  >
                    {error.error_code ?? "—"}
                  </TableCell>
                  <TableCell className="hidden text-right tabular-nums md:table-cell">
                    {formatLatency(error.latency_ms)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Section>

      <Section
        id="series-heading"
        title="近 7 日请求"
        meta={`合计 ${formatNumber(weekTotal)} 次`}
      >
        <div className="relative h-[200px]">
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
      </Section>

      <Section id="providers-heading" title="厂商">
        <Table className="max-w-[600px]">
          <TableHead>
            <TableRow>
              <TableHeaderCell>厂商</TableHeaderCell>
              <TableHeaderCell>账号</TableHeaderCell>
              <TableHeaderCell className="text-right">今日请求</TableHeaderCell>
              <TableHeaderCell className="text-right">失败</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.providers.map((provider) => (
              <TableRow key={provider.code} className="hover:bg-transparent">
                <TableCell>{provider.name}</TableCell>
                <TableCell className="text-meta text-muted">
                  {provider.accounts} / {provider.available_accounts} 可用
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(provider.today_requests)}
                </TableCell>
                <TableCell
                  className={cn(
                    "text-right tabular-nums",
                    provider.today_failures > 0 ? "text-danger" : "text-muted",
                  )}
                >
                  {formatNumber(provider.today_failures)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>

      <footer className="mt-12 border-t border-line pt-4 text-micro text-muted">
        {data.cache.enabled
          ? `缓存已开启，${formatNumber(data.cache.entries)} / ${formatNumber(data.cache.max_entries)} 条，TTL ${data.cache.ttl_seconds} 秒`
          : `缓存已关闭，TTL ${data.cache.ttl_seconds} 秒，上限 ${formatNumber(data.cache.max_entries)} 条`}
      </footer>
    </div>
  );
}
