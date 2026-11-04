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
import { NavLink, Outlet, ScrollRestoration, useNavigate } from "react-router-dom";

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

function NavItems({
  tone = "rail",
  onNavigate,
}: {
  tone?: "rail" | "light";
  onNavigate?: () => void;
}) {
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
                "relative flex h-9 items-center gap-2.5 rounded-sm px-3 text-meta transition-colors focus-visible:outline-[#7fb6da]",
                tone === "rail"
                  ? isActive
                    ? "bg-white/10 font-medium text-white before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-[#7fb6da]"
                    : "text-white/70 hover:bg-white/5 hover:text-white"
                  : isActive
                    ? "bg-mist font-medium text-ink"
                    : "text-ink hover:bg-mist/60",
              )
            }
          >
            <Icon className="size-4 shrink-0" aria-hidden="true" />
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
      <ScrollRestoration />
      <aside className="fixed inset-y-0 left-0 hidden w-[224px] flex-col bg-navy px-4 py-6 md:flex xl:w-[240px]">
        <div className="px-3">
          <p className="text-[17px] font-medium leading-tight tracking-tight text-white">
            OCR Gateway
          </p>
          <p className="mt-1 text-micro text-white/50">管理面板</p>
        </div>
        <div className="mt-9 flex-1">
          <NavItems />
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-white/10 px-3 pt-4">
          <span className="truncate text-meta text-white/80">{auth.username ?? "admin"}</span>
          <button
            type="button"
            onClick={() => void onLogout()}
            className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-meta text-white/60 transition-colors hover:bg-white/5 hover:text-white focus-visible:outline-[#7fb6da]"
          >
            <LogOut className="size-3.5" aria-hidden="true" />
            登出
          </button>
        </div>
      </aside>

      <div className="md:pl-[224px] xl:pl-[240px]">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-paper/95 px-4 backdrop-blur md:hidden">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              aria-label="打开导航"
              onClick={() => setMenuOpen(true)}
            >
              <Menu />
            </Button>
            <span className="text-[15px] font-medium text-ink">OCR Gateway</span>
          </div>
          <span className="text-micro text-muted">{auth.username ?? "admin"}</span>
        </header>

        <main className="mx-auto w-full max-w-[1200px] px-5 py-8 md:px-10 md:py-12">
          <Outlet />
        </main>
      </div>

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent className="left-0 top-0 flex h-full w-[280px] max-w-[85vw] translate-x-0 translate-y-0 flex-col rounded-none border-y-0 border-l-0 p-5">
          <DialogTitle>导航</DialogTitle>
          <div className="mt-6">
            <NavItems tone="light" onNavigate={() => setMenuOpen(false)} />
          </div>
          <div className="mt-auto flex items-center justify-between border-t border-line pt-4">
            <span className="text-meta text-muted">{auth.username ?? "admin"}</span>
            <Button variant="ghost" size="sm" onClick={() => void onLogout()}>
              <LogOut aria-hidden="true" />
              登出
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
