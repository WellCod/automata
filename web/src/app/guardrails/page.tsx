"use client";

import { InstanceGuardrailsPanel } from "@/components/instance-guardrails-panel";

export default function InstanceGuardrailsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Guardrails da instância</h1>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <InstanceGuardrailsPanel />
      </main>
    </div>
  );
}
