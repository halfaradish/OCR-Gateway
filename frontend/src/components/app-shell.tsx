import {
  BarChart3,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Server,
  Settings,
  Users,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/", label: "总览", icon: LayoutDashboard, end: true },
  { to: "/accounts", label: "账号", icon: Server, end: false },
  { to: "/members", label: "成员与 Key", icon: Users, end: false },
  { to: "/usage", label: "用量", icon: BarChart3, end: false },
  { to: "/logs", label: "日志", icon: ScrollText, end: false },
  { to: "/settings", label: "设置", icon: Settings, end: false },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5" aria-label="主导航">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex h-9 items-center gap-2.5 rounded-sm px-3 text-body transition-colors",
                isActive ? "bg-mist text-navy" : "text-ink hover:bg-mist/60",
              )
            }
          >
            <Icon className="size-4" aria-hidden="true" />
            {item.label}
          </NavLink>
        );
      })}
    </nav>
  );
}

export function AppShell() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const onLogout = async () => {
    await auth.logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-[208px] border-r border-line bg-paper px-4 py-5 md:block xl:w-[232px]">
        <div className="mb-8 px-3">
          <p className="text-h2 font-medium leading-tight text-navy">OCR Gateway</p>
          <p className="text-micro text-muted">管理面板</p>
        </div>
        <NavItems />
      </aside>

      <div className="md:pl-[208px] xl:pl-[232px]">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-paper/95 px-4 backdrop-blur md:px-8">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="打开导航"
              onClick={() => setMenuOpen(true)}
            >
              <Menu />
            </Button>
            <span className="text-meta text-muted">准实时数据 · 页面聚焦时自动刷新</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-meta text-muted">{auth.username ?? "admin"}</span>
            <Button variant="ghost" size="sm" onClick={() => void onLogout()}>
              <LogOut aria-hidden="true" />
              登出
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1280px] px-4 py-8 md:px-8">
          <Outlet />
        </main>
      </div>

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent className="left-0 top-0 h-full w-[280px] max-w-[85vw] translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-5">
          <DialogTitle>导航</DialogTitle>
          <div className="mt-6">
            <NavItems onNavigate={() => setMenuOpen(false)} />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
