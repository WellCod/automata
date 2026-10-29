"use client";

import { cn } from "@/lib/utils";
import {
  BarChart3,
  Bell,
  Brain,
  BookOpen,
  KeyRound,
  LayoutGrid,
  LockKeyhole,
  LogOut,
  Plug,
  ShieldCheck,
  UserCog,
  Users,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { usePendingApprovals } from "@/lib/api/approvals";
import { useMe } from "@/lib/api/users";
import { ThemeToggle } from "./theme";

const navItems = [
  { href: "/", label: "Agentes", icon: LayoutGrid, exact: true },
  { href: "/times", label: "Times", icon: Users, exact: false },
  { href: "/workflows", label: "Workflows", icon: Workflow, exact: false },
  { href: "/analytics", label: "Analytics", icon: BarChart3, exact: true },
  { href: "/conhecimento", label: "Conhecimento", icon: BookOpen, exact: false },
  { href: "/mcp", label: "Servidores MCP", icon: Plug, exact: true },
  { href: "/aprovacoes", label: "Aprovações", icon: ShieldCheck, exact: true },
  { href: "/integracoes", label: "Integrações", icon: KeyRound, exact: true },
  { href: "/alertas", label: "Alertas", icon: Bell, exact: true, ownerOnly: true },
  { href: "/usuarios", label: "Usuários", icon: UserCog, exact: true, ownerOnly: true },
  { href: "/chaves", label: "Chaves", icon: LockKeyhole, exact: true, ownerOnly: true },
];

function LogoMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <rect width="18" height="18" rx="4" className="fill-accent" />
      <rect x="4" y="4" width="4" height="4" className="fill-accent-foreground" />
      <rect x="10" y="4" width="4" height="4" className="fill-accent-foreground" />
      <rect x="4" y="10" width="4" height="4" className="fill-accent-foreground" />
      <rect x="10" y="10" width="2" height="2" className="fill-accent-foreground" />
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: pending } = usePendingApprovals();
  const { data: me } = useMe();
  // a API recusa quem não é owner; o item só some para não levar a uma página vazia
  const visible = navItems.filter((item) => !item.ownerOnly || me?.role === "owner");

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
        {visible.map(({ href, label, icon: Icon, exact }) => {
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
              {href === "/aprovacoes" && pending && pending.length > 0 && (
                <span
                  className="ml-auto rounded border border-amber-500/50 px-1.5 text-[11px] text-amber-600 dark:text-amber-400"
                  aria-label={`${pending.length} aguardando`}
                >
                  {pending.length}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="border-sidebar-border flex items-center justify-between border-t px-3 py-2">
        <span
          className="text-muted-foreground min-w-0 truncate text-[11px]"
          title={me?.email ?? ""}
        >
          {me?.email ?? "v0.1"}
        </span>
        <div className="flex items-center gap-1">
          <Link
            href="/minhas-memorias"
            aria-label="Minhas memórias"
            title="Minhas memórias"
            className="text-muted-foreground hover:border-border hover:text-foreground focus-visible:ring-ring/50 flex h-6 w-6 items-center justify-center rounded border border-transparent transition-colors focus-visible:ring-2 focus-visible:outline-none"
          >
            <Brain className="h-3.5 w-3.5" />
          </Link>
          <ThemeToggle />
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
