"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { toast } from "sonner";
import { detailOf, PasswordForm } from "@/components/password-form";

export default function ChangePasswordPage() {
  return (
    <Suspense>
      <ChangePassword />
    </Suspense>
  );
}

function ChangePassword() {
  const router = useRouter();
  // senha provisória do owner: o painel só abre depois da troca (ADR-0045)
  const forced = useSearchParams().get("obrigatoria") === "1";

  async function submit(values: { current_password: string; new_password: string }) {
    const res = await fetch("/api/auth/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!res.ok) return detailOf(res, "Não foi possível trocar a senha.");
    toast.success("Senha trocada. As outras sessões foram encerradas.");
    router.push("/");
    router.refresh();
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="flex w-full max-w-sm flex-col gap-4">
        <h1 className="text-foreground text-sm font-medium">Trocar senha</h1>
        <p className="text-muted-foreground text-[13px]">
          {forced
            ? "Sua senha foi definida por quem administra o painel. Escolha uma nova para continuar."
            : "A troca encerra as suas outras sessões abertas."}
        </p>
        <PasswordForm askCurrent submitLabel="Trocar senha" onSubmit={submit} />
        {!forced && (
          <Link href="/" className="text-muted-foreground hover:text-foreground text-[12px]">
            Voltar ao painel
          </Link>
        )}
      </div>
    </div>
  );
}
