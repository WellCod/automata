"use client";

import { Tooltip } from "@base-ui/react/tooltip";
import { Info } from "lucide-react";
import type * as React from "react";
import { cn } from "@/lib/utils";

interface Props {
  // texto visível do gatilho (ex.: "p50"); sem ele, só o ícone
  label?: React.ReactNode;
  // nome acessível do gatilho, ex.: "O que é p50"
  ariaLabel: string;
  children: React.ReactNode;
  className?: string;
}

// Explicação curta no hover e no foco do teclado (Base UI cuida de aria-describedby).
function InfoHint({ label, ariaLabel, children, className }: Props) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger
        delay={150}
        aria-label={ariaLabel}
        render={<button type="button" />}
        className={cn(
          "text-muted-foreground hover:text-foreground focus-visible:ring-ring inline-flex items-center gap-1 rounded text-[11px] focus-visible:ring-2 focus-visible:outline-none",
          className,
        )}
      >
        {label}
        <Info className="h-3 w-3" aria-hidden />
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Positioner sideOffset={6}>
          <Tooltip.Popup className="border-border bg-popover text-popover-foreground z-50 max-w-64 rounded border px-2.5 py-1.5 text-[12px] leading-snug shadow-md">
            {children}
          </Tooltip.Popup>
        </Tooltip.Positioner>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export { InfoHint };
