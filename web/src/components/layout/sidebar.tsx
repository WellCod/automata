"use client";

import { cn } from "@/lib/utils";
import { useTheme } from "@/components/layout/theme-provider";
import { LayoutGrid, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [{ href: "/", label: "Agentes", icon: LayoutGrid, exact: true }];

function LogoMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
      <rect width="64" height="64" rx="8" fill="#0B0B0B" />
      <g fill="#25E0C8">
        <g opacity="0.2">
          <rect x="12" y="12" width="12" height="12" rx="2" />
          <rect x="40" y="12" width="12" height="12" rx="2" />
          <rect x="12" y="26" width="12" height="12" rx="2" />
          <rect x="26" y="26" width="12" height="12" rx="2" />
        </g>
        <rect x="26" y="12" width="12" height="12" rx="2" />
        <rect x="40" y="26" width="12" height="12" rx="2" />
        <rect x="12" y="40" width="12" height="12" rx="2" />
        <rect x="26" y="40" width="12" height="12" rx="2" />
        <rect x="40" y="40" width="12" height="12" rx="2" />
      </g>
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();

  return (
    <aside className="border-border bg-sidebar fixed inset-y-0 left-0 z-20 flex w-[200px] flex-col border-r">
      <div className="border-border flex h-11 items-center gap-2 border-b px-3">
        <LogoMark />
        <span className="text-foreground text-[13px] font-medium tracking-wider uppercase">
          automata
        </span>
      </div>

      <nav className="flex-1 py-1">
        {navItems.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex h-8 items-center gap-2 px-3 text-[13px] transition-colors",
                active ? "text-accent" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-border flex items-center justify-between border-t px-3 py-2">
        <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">v0.1</span>
        <button
          type="button"
          onClick={toggle}
          aria-label={theme === "dark" ? "Modo claro" : "Modo escuro"}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </button>
      </div>
    </aside>
  );
}
