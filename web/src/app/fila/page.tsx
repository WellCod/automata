"use client";

import { QueuePanel } from "@/components/queue-panel";

export default function QueuePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Fila</h1>
      </header>
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Runs em background na fila durável. Um job que falhou pode voltar para a fila uma vez por
          clique; agentes marcados como idempotentes no controle do run voltam sozinhos. Só owners
          veem esta página.
        </p>
        <QueuePanel />
      </main>
    </div>
  );
}
