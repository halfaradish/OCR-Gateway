import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div>
        <p className="text-h2 font-medium text-navy">页面不存在</p>
        <p className="mt-1 text-meta text-muted">请检查地址，或返回总览。</p>
        <Link to="/" className="mt-4 inline-block text-meta text-blue hover:underline">
          返回总览
        </Link>
      </div>
    </div>
  );
}
