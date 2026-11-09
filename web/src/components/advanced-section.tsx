"use client";

import { ChevronDown } from "lucide-react";
import type * as React from "react";

interface Props {
  // o que tem dentro, numa linha: quem não abre ainda sabe o que há ali
  summary: string;
  // abre sozinho quando um campo de dentro tem erro de validação
  forceOpen?: boolean;
  children: React.ReactNode;
}

// Seções avançadas recolhidas: a configuração tinha 4300 px e o mais editado ficava no fim
export function AdvancedSection({ summary, forceOpen, children }: Props) {
  return (
    <details open={forceOpen || undefined} className="group border-border rounded border">
      <summary className="hover:bg-muted/40 flex cursor-pointer list-none items-center justify-between gap-3 rounded px-4 py-3 [&::-webkit-details-marker]:hidden">
        <span className="flex flex-col gap-0.5">
          <span className="text-foreground text-[13px] font-medium">Configurações avançadas</span>
          <span className="text-muted-foreground text-[12px]">{summary}</span>
        </span>
        <ChevronDown
          className="text-muted-foreground h-4 w-4 flex-none transition-transform group-open:rotate-180"
          aria-hidden
        />
      </summary>
      <div className="flex flex-col gap-6 px-4 pt-2 pb-4">{children}</div>
    </details>
  );
}
