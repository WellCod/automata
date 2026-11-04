"use client";

import { DataSubjectsPanel } from "@/components/data-subjects-panel";

export default function DataSubjectsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Titulares</h1>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Pedidos da LGPD sobre uma pessoa: o que a instância guarda dela, uma cópia de tudo e a
          exclusão. O titular é o id do usuário no run: o e-mail de quem usa o painel ou o id que o
          sistema integrado manda. Só owners veem esta página.
        </p>
        <DataSubjectsPanel />
      </main>
    </div>
  );
}
