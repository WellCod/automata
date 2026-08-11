"use client";

import { cn } from "@/lib/utils";
import { LayoutGrid, LogOut, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "./theme-provider";

const navItems = [{ href: "/", label: "Agentes", icon: LayoutGrid, exact: true }];

function LogoMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <rect width="18" height="18" rx="2" fill="#25E0C8" />
      <rect x="4" y="4" width="4" height="4" fill="#0B0B0B" />
      <rect x="10" y="4" width="4" height="4" fill="#0B0B0B" />
      <rect x="4" y="10" width="4" height="4" fill="#0B0B0B" />
      <rect x="10" y="10" width="2" height="2" fill="#0B0B0B" />
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const router = useRouter();
  const isClient = useSyncExternalStore(() => () => {}, () => true, () => false);
  const isDark = isClient && theme === "dark";

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  return (
    <aside className="border-sidebar-border bg-sidebar fixed inset-y-0 left-0 z-20 flex w-[200px] flex-col border-r">
      <div className="border-sidebar-border flex h-11 items-center gap-2 border-b px-3">
        <LogoMark />
        <span className="text-foreground text-[13px] font-medium tracking-tight">automata</span>
      </div>

      <nav className="flex-1 px-3 py-2">
        {navItems.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex h-8 items-center gap-2 px-0 text-[13px] transition-colors",
                active ? "text-accent" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-sidebar-border flex items-center justify-between border-t px-3 py-2">
        <span className="text-muted-foreground text-[11px] font-medium tracking-[0.05em] uppercase">
          v0.1
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={toggle}
            aria-label={isDark ? "Mudar para tema claro" : "Mudar para tema escuro"}
            className="text-muted-foreground hover:border-border hover:text-foreground focus-visible:ring-ring/50 flex h-6 w-6 items-center justify-center rounded border border-transparent transition-colors focus-visible:ring-2 focus-visible:outline-none"
          >
            {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          </button>
          <button
            type="button"
            onClick={() => void handleLogout()}
            aria-label="Sair"
            className="text-muted-foreground hover:border-border hover:text-foreground focus-visible:ring-ring/50 flex h-6 w-6 items-center justify-center rounded border border-transparent transition-colors focus-visible:ring-2 focus-visible:outline-none"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
