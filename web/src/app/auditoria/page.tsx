"use client";

import { AuditLog } from "@/components/audit-log";

export default function AuditPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Auditoria</h1>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Quem mudou o quê, quando e de onde: publicações, rollbacks, canário, piso de guardrails,
          usuários, tokens, titulares, orçamentos e decisões de aprovação. Tentativas recusadas
          também aparecem. O conteúdo enviado não é guardado. Só owners veem esta página.
        </p>
        <AuditLog />
      </main>
    </div>
  );
}
