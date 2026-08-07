"use client";

import { cn } from "@/lib/utils";
import { useTheme } from "@/components/layout/theme-provider";
import { Bot, LayoutGrid, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [{ href: "/", label: "Agentes", icon: LayoutGrid, exact: true }];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();

  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-52 flex-col border-r border-zinc-200 bg-white transition-colors duration-200 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex h-14 items-center gap-2.5 border-b border-zinc-100 px-4 dark:border-zinc-800">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-900 dark:bg-zinc-100">
          <Bot className="h-4 w-4 text-white dark:text-zinc-900" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          automata
        </span>
      </div>

      <nav className="flex-1 px-2 py-3">
        {navItems.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/50 dark:hover:text-zinc-100",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3 dark:border-zinc-800">
        <p className="text-xs text-zinc-400 dark:text-zinc-600">v0.1</p>
        <button
          type="button"
          onClick={toggle}
          aria-label={theme === "dark" ? "Modo claro" : "Modo escuro"}
          className="rounded-md p-1.5 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700 dark:text-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
