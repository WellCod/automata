"use client";

import { MyDataPanel } from "@/components/my-data-panel";

export default function MyDataPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Meus dados</h1>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          O que a instância guarda das suas conversas com os agentes: histórico, memória e consumo.
          Você pode baixar uma cópia ou apagar. Apagar não remove a sua conta do painel.
        </p>
        <MyDataPanel />
      </main>
    </div>
  );
}
