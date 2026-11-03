import { PageHeader } from "@/components/page-header";

export default function Placeholder() {
  return (
    <div>
      <PageHeader title="日志" description="请求日志会出现在这里。" />
      <p className="text-meta text-muted">该页面由后续切片实现。</p>
    </div>
  );
}
