"use client";

import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LogoMark, Sidebar, SIDEBAR_ID } from "./sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const withSidebar = pathname !== "/login";
  // abaixo de md a barra lateral vira gaveta, aberta pelo botão da barra de topo
  const [open, setOpen] = useState(false);
  const [openedAt, setOpenedAt] = useState(pathname);

  // navegar fecha a gaveta; ajuste no render em vez de efeito, como pede o React
  if (open && openedAt !== pathname) {
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!withSidebar) return <div className="min-h-full flex-1">{children}</div>;

  return (
    <div className="flex min-h-full min-w-0 flex-1 flex-col">
      <div className="border-border bg-background flex h-11 items-center gap-2 border-b px-3 md:hidden">
        <button
          type="button"
          onClick={() => {
            setOpenedAt(pathname);
            setOpen(true);
          }}
          aria-label="Abrir menu"
          aria-expanded={open}
          aria-controls={SIDEBAR_ID}
          className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 -ml-1 flex h-9 w-9 items-center justify-center rounded focus-visible:ring-2 focus-visible:outline-none"
        >
          <Menu className="h-5 w-5" />
        </button>
        <LogoMark />
        <span className="text-foreground text-[13px] font-medium tracking-tight">automata</span>
      </div>
      {open && (
        <div
          aria-hidden
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-20 bg-black/40 md:hidden"
        />
      )}
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="min-w-0 flex-1 md:pl-[200px]">{children}</div>
    </div>
  );
}
