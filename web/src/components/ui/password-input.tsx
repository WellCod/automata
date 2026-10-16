"use client";

import { Eye, EyeOff } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

type Props = Omit<React.ComponentProps<"input">, "type">;

// Senha oculta por padrão, com botão para conferir o que foi digitado.
// Sem o type="password" a senha aparece para quem olha a tela e fica no histórico
// de preenchimento do navegador.
function PasswordInput({ className, ...props }: Props) {
  const [visible, setVisible] = React.useState(false);
  return (
    // min-w: sem ele, numa linha com botões o wrapper encolhe até sumir o texto
    <div className="relative w-full min-w-40 flex-1">
      <input
        data-slot="password-input"
        type={visible ? "text" : "password"}
        spellCheck={false}
        autoCapitalize="off"
        className={cn(className, "pr-9")}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Ocultar senha" : "Mostrar senha"}
        aria-pressed={visible}
        title={visible ? "Ocultar senha" : "Mostrar senha"}
        className="text-muted-foreground hover:text-foreground focus-visible:ring-ring absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r focus-visible:ring-2 focus-visible:outline-none"
      >
        {visible ? (
          <EyeOff className="h-3.5 w-3.5" aria-hidden />
        ) : (
          <Eye className="h-3.5 w-3.5" aria-hidden />
        )}
      </button>
    </div>
  );
}

export { PasswordInput };
