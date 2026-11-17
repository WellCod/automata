"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { inputCls } from "@/components/password-form";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await fetch("/api/auth/password/forgot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.status === 429) setError("Muitas tentativas. Aguarde um minuto.");
      else if (!res.ok) setError("Informe um e-mail válido.");
      else setSent(true);
    } catch {
      setError("Erro de conexão. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="flex w-full max-w-sm flex-col gap-4">
        <h1 className="text-foreground text-sm font-medium">Esqueci minha senha</h1>
        {sent ? (
          <p className="text-muted-foreground text-[13px]">
            Se o e-mail tiver conta com senha no painel, enviamos um link para escolher outra. O
            link vale por 30 minutos. Quem entra pelo SSO troca a senha no provedor.
          </p>
        ) : (
          <form onSubmit={submit} noValidate className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label htmlFor="email" className="text-foreground text-[13px] font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputCls}
              />
            </div>
            {error && <p className="text-destructive text-[11px]">{error}</p>}
            <Button type="submit" disabled={busy || !email} variant="strong" className="h-8 w-full">
              {busy ? "Enviando…" : "Enviar link"}
            </Button>
          </form>
        )}
        <Link href="/login" className="text-muted-foreground hover:text-foreground text-[12px]">
          Voltar ao login
        </Link>
      </div>
    </div>
  );
}
