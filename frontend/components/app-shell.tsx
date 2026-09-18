"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useTheme } from "@/hooks/use-theme";

const NAV_ITEMS = [
  { href: "/dashboard", label: "대시보드" },
  { href: "/refund-cases", label: "환불 케이스" },
  { href: "/knowledge-base", label: "지식베이스" },
];

function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex w-56 shrink-0 flex-col bg-panel text-panel-foreground">
      <div className="flex h-16 items-center border-b border-panel-border px-5">
        <span className="text-[15px] font-semibold tracking-tight">AgentOps</span>
      </div>
      <nav className="flex flex-col gap-0.5 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-sm px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-white/10 text-panel-foreground"
                  : "text-panel-secondary hover:bg-white/5 hover:text-panel-foreground"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto border-t border-panel-border px-5 py-4 text-xs text-panel-secondary">
        CS 환불 자동화 에이전트
      </div>
    </aside>
  );
}

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "라이트 모드로 전환" : "다크 모드로 전환"}
      className="flex items-center gap-2 rounded-sm border border-border-subtle px-3 py-1.5 text-xs text-text-secondary hover:text-foreground"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${isDark ? "bg-accent" : "bg-status-progress"}`} />
      {isDark ? "다크" : "라이트"}
    </button>
  );
}

function Topbar({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border-subtle px-8">
      <div>
        <h1 className="text-base font-semibold">{title}</h1>
        {subtitle && <p className="text-xs text-text-secondary">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-4">
        {actions}
        <ThemeToggle />
      </div>
    </header>
  );
}

export function AppShell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} subtitle={subtitle} actions={actions} />
        <main className="flex flex-1 flex-col gap-8 px-8 py-8">{children}</main>
      </div>
    </div>
  );
}
