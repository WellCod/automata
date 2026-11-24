"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { toast } from "sonner";
import { detailOf, PasswordForm } from "@/components/password-form";

// useSearchParams pede Suspense na renderização estática
export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPassword />
    </Suspense>
  );
}

function ResetPassword() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";

  async function submit(values: { new_password: string }) {
    const response = await fetch("/api/auth/password/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: values.new_password }),
    });
    if (!response.ok) return detailOf(response, "Link inválido ou vencido. Peça outro.");
    toast.success("Senha nova salva.");
    router.push("/");
    router.refresh();
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="flex w-full max-w-sm flex-col gap-4">
        <h1 className="text-foreground text-sm font-medium">Escolher nova senha</h1>
        {token ? (
          <PasswordForm askCurrent={false} submitLabel="Salvar senha" onSubmit={submit} />
        ) : (
          <p className="text-muted-foreground text-[13px]">
            Link incompleto. Abra de novo o link do e-mail ou peça outro.
          </p>
        )}
        <Link
          href="/esqueci-senha"
          className="text-muted-foreground hover:text-foreground text-[12px]"
        >
          Pedir outro link
        </Link>
      </div>
    </div>
  );
}
