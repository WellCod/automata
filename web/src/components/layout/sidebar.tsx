"use client";

import { cn } from "@/lib/utils";
import { Bot, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [{ href: "/", label: "Agentes", icon: LayoutGrid, exact: true }];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-52 flex-col border-r border-zinc-200 bg-white">
      <div className="flex h-14 items-center gap-2.5 border-b border-zinc-100 px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-900">
          <Bot className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-zinc-900">automata</span>
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
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-zinc-100 px-4 py-3">
        <p className="text-xs text-zinc-400">v0.1</p>
      </div>
    </aside>
  );
}
