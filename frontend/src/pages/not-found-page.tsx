import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-5">
      <div className="w-full max-w-[420px] border-t-2 border-navy pt-6">
        <p className="text-micro tabular-nums text-muted">404</p>
        <h1 className="mt-2 text-h1 font-medium tracking-tight text-ink">页面不存在</h1>
        <p className="mt-2 text-meta text-muted">请检查地址，或返回总览。</p>
        <Link
          to="/"
          className="mt-6 inline-flex h-9 items-center rounded-sm bg-navy px-4 text-body font-medium text-white hover:bg-navy-deep"
        >
          返回总览
        </Link>
      </div>
    </main>
  );
}
