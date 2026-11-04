export const PROVIDER_LABELS: Record<string, string> = {
  baidu: "百度智能云",
  tencent: "腾讯云",
  auto: "自动路由",
};

export function providerLabel(code: string): string {
  return PROVIDER_LABELS[code] ?? code;
}
