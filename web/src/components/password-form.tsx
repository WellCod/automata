"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";

export const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

// mesma regra da API (_password_complexity): 12 caracteres, maiúscula e dígito
const newPassword = z
  .string()
  .min(12, "Mínimo de 12 caracteres")
  .regex(/[A-Z]/, "Inclua ao menos uma letra maiúscula")
  .regex(/\d/, "Inclua ao menos um dígito");

function schemaFor(askCurrent: boolean) {
  return z
    .object({
      current_password: askCurrent ? z.string().min(1, "Informe a senha atual") : z.string(),
      new_password: newPassword,
      confirm: z.string(),
    })
    .refine((v) => v.new_password === v.confirm, {
      path: ["confirm"],
      message: "As senhas não conferem",
    });
}

type Values = { current_password: string; new_password: string; confirm: string };

type Props = {
  askCurrent: boolean;
  submitLabel: string;
  onSubmit: (values: { current_password: string; new_password: string }) => Promise<string | null>;
};

// devolve null no sucesso ou a mensagem de erro para mostrar
export function PasswordForm({ askCurrent, submitLabel, onSubmit }: Props) {
  const [error, setError] = useState("");
  const form = useForm<Values>({
    resolver: zodResolver(schemaFor(askCurrent)),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });
  const errors = form.formState.errors;

  async function submit(values: Values) {
    setError("");
    const failure = await onSubmit({
      current_password: values.current_password,
      new_password: values.new_password,
    });
    if (failure) setError(failure);
  }

  return (
    <form onSubmit={form.handleSubmit(submit)} noValidate className="flex flex-col gap-4">
      {askCurrent && (
        <div className="flex flex-col gap-1">
          <label htmlFor="current_password" className="text-foreground text-[13px] font-medium">
            Senha atual
          </label>
          <PasswordInput
            {...form.register("current_password")}
            id="current_password"
            autoComplete="current-password"
            className={inputCls}
          />
          {errors.current_password && (
            <p className="text-destructive text-[11px]">{errors.current_password.message}</p>
          )}
        </div>
      )}
      <div className="flex flex-col gap-1">
        <label htmlFor="new_password" className="text-foreground text-[13px] font-medium">
          Nova senha
        </label>
        <PasswordInput
          {...form.register("new_password")}
          id="new_password"
          autoComplete="new-password"
          className={inputCls}
        />
        <p className="text-muted-foreground text-[11px]">
          12 caracteres ou mais, com letra maiúscula e dígito.
        </p>
        {errors.new_password && (
          <p className="text-destructive text-[11px]">{errors.new_password.message}</p>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="confirm" className="text-foreground text-[13px] font-medium">
          Repita a nova senha
        </label>
        <PasswordInput
          {...form.register("confirm")}
          id="confirm"
          autoComplete="new-password"
          className={inputCls}
        />
        {errors.confirm && <p className="text-destructive text-[11px]">{errors.confirm.message}</p>}
      </div>
      {error && <p className="text-destructive text-[11px]">{error}</p>}
      <Button
        type="submit"
        disabled={form.formState.isSubmitting}
        variant="strong"
        className="mt-2 h-8 w-full"
      >
        {form.formState.isSubmitting ? "Salvando…" : submitLabel}
      </Button>
    </form>
  );
}

export async function detailOf(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // corpo vazio
  }
  return res.status === 429 ? "Muitas tentativas. Aguarde um minuto." : fallback;
}
