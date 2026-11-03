export type ProviderCode = "baidu" | "tencent";
export type AccountState = "active" | "cooling" | "invalid" | "quota_exhausted" | "disabled";

export interface QuotaSlice {
  used: number;
  limit: number | null;
  period_key: string;
}

export interface QuotaUsage {
  daily: QuotaSlice;
  monthly: QuotaSlice;
  total: QuotaSlice;
}

export interface MeResponse {
  username: string;
  csrf_token?: string;
}

export interface LoginResponse {
  token: string;
  expires_in: number;
  csrf_token: string;
}

export interface ProviderRow {
  code: ProviderCode;
  name: string;
  accounts: number;
  available_accounts: number;
  today_requests: number;
  today_failures: number;
}

export interface AccountQuotaRow {
  id: number;
  name: string;
  provider: string;
  state: string;
  quota_usage: QuotaUsage;
}

export interface RecentError {
  id: number;
  request_id: string;
  provider: string;
  account_id: number | null;
  account_name: string | null;
  error_code: string | null;
  latency_ms: number;
  created_at: string;
}

export interface SeriesRow {
  date: string;
  requests: number;
  success: number;
  failure: number;
  cached: number;
  quota_used: number;
  avg_latency_ms: number | null;
}

export interface Overview {
  generated_at: string;
  today: {
    requests: number;
    success: number;
    failure: number;
    cached: number;
    quota_used: number;
    success_rate: number | null;
    cache_hit_rate: number | null;
    avg_latency_ms: number | null;
    auto_failures: number;
  };
  providers: ProviderRow[];
  accounts: AccountQuotaRow[];
  recent_errors: RecentError[];
  cache: { enabled: boolean; entries: number; ttl_seconds: number; max_entries: number };
  series: SeriesRow[];
}

export interface Account {
  id: number;
  provider: ProviderCode;
  name: string;
  owner_id: number | null;
  owner_name: string | null;
  priority: number;
  weight: number;
  enabled: boolean;
  timeout_ms: number;
  max_concurrency: number;
  qps_limit: number | null;
  quota_daily: number | null;
  quota_monthly: number | null;
  quota_total: number | null;
  quota_unit: string;
  quota_usage: QuotaUsage;
  reset_day: number;
  state: AccountState;
  last_error_code: string | null;
  last_error_message: string | null;
  ewma_latency_ms: number;
  last_used_at: string | null;
  created_at: string;
  credential_fields: Record<string, string>;
}

export interface Member {
  id: number;
  name: string;
  enabled: boolean;
  created_at: string;
}

export interface ApiKeyRow {
  id: number;
  user_id: number;
  name: string;
  key_prefix: string;
  enabled: boolean;
  daily_limit: number | null;
  rpm_limit: number | null;
  last_used_at: string | null;
  created_at: string;
}

export interface CreatedApiKey extends ApiKeyRow {
  key: string;
}

export interface SummaryRow {
  key: number | string | null;
  label: string | null;
  requests: number;
  success: number;
  failure: number;
  cached: number;
  quota_used: number;
  avg_latency_ms: number | null;
}

export interface SummaryResponse {
  from: string;
  to: string;
  group_by: "user" | "provider" | "account";
  rows: SummaryRow[];
}

export interface SeriesResponse {
  from: string;
  to: string;
  bucket: "day";
  rows: SeriesRow[];
}

export interface LogRow {
  id: number;
  request_id: string;
  user_id: number | null;
  user_name: string | null;
  api_key_id: number | null;
  account_id: number | null;
  account_name: string | null;
  provider: string;
  success: boolean;
  error_code: string | null;
  latency_ms: number;
  quota_used: number;
  cached: boolean;
  image_hash: string | null;
  created_at: string;
}

export interface LogsResponse {
  limit: number;
  offset: number;
  total: number;
  rows: LogRow[];
}

export interface SettingsEditable {
  cache_enabled: boolean;
  cache_ttl_seconds: number;
  cache_max_entries: number;
  request_deadline_ms: number;
  default_timeout_ms: number;
}

export interface SettingsReadonly {
  api_auth_enabled: boolean;
  version: string;
  max_upload_bytes: number;
  max_image_pixels: number;
  max_concurrent_requests: number;
  session_ttl_seconds: number;
  frontend_built: boolean;
}

export interface SettingsResponse {
  editable: SettingsEditable;
  readonly: SettingsReadonly;
}

export interface SettingsUpdateResponse {
  settings: SettingsEditable;
  cache_cleared: boolean;
}

export interface QuotaTemplate {
  provider: string;
  name: string;
  quota_daily?: number | null;
  quota_monthly?: number | null;
  notes?: string | null;
}

export interface QuotaTemplatesResponse {
  disclaimer: string;
  providers: QuotaTemplate[];
}

export interface TestAccountResponse {
  ok: boolean;
  provider: string;
  text?: string;
  error_code?: string;
  message?: string;
  latency_ms: number;
}

export type GroupBy = "user" | "provider" | "account";
export type UsageMetric = "requests" | "success_rate" | "avg_latency";
