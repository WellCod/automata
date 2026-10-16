"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";

const schema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "Senha obrigatória"),
});

type FormValues = z.infer<typeof schema>;

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

function LogoMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <rect width="18" height="18" rx="2" fill="#25E0C8" />
      <rect x="4" y="4" width="4" height="4" fill="#0B0B0B" />
      <rect x="10" y="4" width="4" height="4" fill="#0B0B0B" />
      <rect x="4" y="10" width="4" height="4" fill="#0B0B0B" />
      <rect x="10" y="10" width="2" height="2" fill="#0B0B0B" />
    </svg>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState("");

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  async function onSubmit(values: FormValues) {
    setServerError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });

      if (!res.ok) {
        setServerError("Credenciais inválidas");
        return;
      }

      router.push("/");
      router.refresh();
    } catch {
      setServerError("Erro de conexão. Tente novamente.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2">
          <LogoMark />
          <span className="text-foreground text-[13px] font-medium tracking-tight">automata</span>
        </div>

        <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="email" className="text-foreground text-[13px] font-medium">
              Email
            </label>
            <input
              {...form.register("email")}
              id="email"
              type="email"
              autoComplete="email"
              className={inputCls}
            />
            {form.formState.errors.email && (
              <p className="text-destructive text-[11px]">{form.formState.errors.email.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-foreground text-[13px] font-medium">
              Senha
            </label>
            <PasswordInput
              {...form.register("password")}
              id="password"
              autoComplete="current-password"
              className={inputCls}
            />
            {form.formState.errors.password && (
              <p className="text-destructive text-[11px]">
                {form.formState.errors.password.message}
              </p>
            )}
          </div>

          {serverError && <p className="text-destructive text-[11px]">{serverError}</p>}

          <Button
            type="submit"
            disabled={form.formState.isSubmitting}
            variant="strong"
            className="mt-2 h-8 w-full"
          >
            {form.formState.isSubmitting ? "Entrando…" : "Entrar"}
          </Button>
        </form>
      </div>
    </div>
  );
}
