"use client";

import { KeyRotationPanel } from "@/components/key-rotation-panel";

export default function KeysPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Chaves</h1>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Troca da chave que assina os tokens e da chave que cifra os segredos guardados. Durante a
          troca, a chave anterior só serve para ler, e aqui aparece o que ainda depende dela. Só
          owners veem esta página.
        </p>
        <KeyRotationPanel />
      </main>
    </div>
  );
}
