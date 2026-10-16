"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Badge } from "@/components/ui/status-badge";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import {
  ROLE_HINTS,
  ROLE_LABELS,
  temporaryPassword,
  type UserAccount,
  type UserRole,
  useMe,
  useUsers,
} from "@/lib/api/users";

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

const ROLES: UserRole[] = ["owner", "editor", "viewer"];

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: ["users"] });
}

function NewUserForm({ onDone }: { onDone: () => void }) {
  const invalidate = useInvalidate();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("editor");
  const [password, setPassword] = useState(temporaryPassword);

  const create = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/users", { body: { email, role, password } });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao criar usuário"));
      return res.data!;
    },
    onSuccess: (user) => {
      toast.success(`${user.email} criado`);
      invalidate();
      onDone();
    },
  });

  return (
    <form
      aria-label="Novo usuário"
      className="border-border bg-card flex flex-col gap-4 rounded border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="user-email">E-mail</FieldLabel>
          <input
            id="user-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="pessoa@empresa.com"
            className={inputCls}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="user-role">Papel</FieldLabel>
          <select
            id="user-role"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className={inputCls}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
          <FieldDescription>{ROLE_HINTS[role]}</FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="user-password">Senha temporária</FieldLabel>
          <div className="flex gap-2">
            <PasswordInput
              id="user-password"
              required
              minLength={12}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${inputCls} font-mono`}
            />
            <Button size="sm" variant="muted" onClick={() => setPassword(temporaryPassword())}>
              Gerar
            </Button>
          </div>
          <FieldDescription>
            Mínimo de 12 caracteres, com maiúscula e número. Repasse à pessoa por um canal seguro.
          </FieldDescription>
        </Field>
      </FieldGroup>
      {create.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {create.error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="muted" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" variant="strong" disabled={create.isPending}>
          {create.isPending ? "Criando…" : "Criar usuário"}
        </Button>
      </div>
    </form>
  );
}

function UserRow({ user, isSelf }: { user: UserAccount; isSelf: boolean }) {
  const invalidate = useInvalidate();
  const [mode, setMode] = useState<"password" | "remove" | null>(null);
  const [password, setPassword] = useState("");

  const update = useMutation({
    mutationFn: async (body: { role?: UserRole; is_active?: boolean }) => {
      const res = await client.PATCH("/api/v1/users/{user_id}", {
        params: { path: { user_id: user.id } },
        body,
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao alterar usuário"));
      return res.data!;
    },
    onSuccess: (u) => {
      toast.success(`${u.email} atualizado; sessões abertas encerradas`);
      invalidate();
    },
    onError: (e) => toast.error(e.message),
  });

  const reset = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/users/{user_id}/password", {
        params: { path: { user_id: user.id } },
        body: { password },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao redefinir senha"));
    },
    onSuccess: () => {
      toast.success(`Senha de ${user.email} redefinida`);
      setMode(null);
      setPassword("");
    },
  });

  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/users/{user_id}", {
        params: { path: { user_id: user.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover"));
    },
    onSuccess: () => {
      toast.success(`${user.email} removido`);
      invalidate();
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <tr className="border-border border-b align-top last:border-0">
      <td className="px-4 py-2.5">
        <div className="flex flex-col gap-0.5">
          <span className="text-foreground text-[13px] font-medium">
            {user.email}
            {isSelf && <span className="text-muted-foreground font-normal"> (você)</span>}
          </span>
          <span className="text-muted-foreground text-[11px]">
            último acesso: {formatDate(user.last_login_at)}
          </span>
        </div>
        {mode === "password" && (
          <form
            className="mt-2 flex flex-col gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              reset.mutate();
            }}
          >
            <div className="flex flex-wrap gap-2">
              <PasswordInput
                aria-label={`Nova senha de ${user.email}`}
                required
                minLength={12}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`${inputCls} font-mono`}
              />
              <Button size="sm" variant="muted" onClick={() => setPassword(temporaryPassword())}>
                Gerar
              </Button>
              <Button size="sm" type="submit" variant="strong" disabled={reset.isPending}>
                Salvar
              </Button>
              <Button size="sm" variant="muted" onClick={() => setMode(null)}>
                Cancelar
              </Button>
            </div>
            {reset.isError && (
              <p className="text-destructive text-[11px]" role="alert">
                {reset.error.message}
              </p>
            )}
          </form>
        )}
      </td>
      <td className="px-4 py-2.5">
        <select
          aria-label={`Papel de ${user.email}`}
          value={user.role}
          disabled={update.isPending}
          onChange={(e) => update.mutate({ role: e.target.value as UserRole })}
          className="border-border text-foreground focus:border-accent rounded border bg-[var(--input)] px-2 py-1 text-[13px] focus:outline-none"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2.5">
        <Badge tone={user.is_active ? "active" : "neutral"}>
          {user.is_active ? "Ativo" : "Desativado"}
        </Badge>
      </td>
      <td className="px-4 py-2.5">
        <div className="flex flex-wrap justify-end gap-2">
          {mode === "remove" ? (
            <>
              <Button size="xs" variant="destructive" onClick={() => remove.mutate()}>
                Confirmar remoção
              </Button>
              <Button size="xs" variant="muted" onClick={() => setMode(null)}>
                Manter
              </Button>
            </>
          ) : (
            <>
              <Button size="xs" variant="muted" onClick={() => setMode("password")}>
                Redefinir senha
              </Button>
              <Button
                size="xs"
                variant={user.is_active ? "subtleDestructive" : "default"}
                disabled={update.isPending}
                onClick={() => update.mutate({ is_active: !user.is_active })}
              >
                {user.is_active ? "Desativar" : "Reativar"}
              </Button>
              {!user.is_active && !isSelf && (
                <Button size="xs" variant="subtleDestructive" onClick={() => setMode("remove")}>
                  Remover
                </Button>
              )}
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function UsersPage() {
  const { data: me } = useMe();
  const { data: users, isPending, isError, error } = useUsers();
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center justify-between border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Usuários</h1>
        <Button variant="accent" onClick={() => setCreating(true)} disabled={creating}>
          Novo usuário
        </Button>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Quem acessa o painel e com qual papel. Mudar papel, desativar ou redefinir senha encerra
          na hora as sessões abertas da pessoa. Para remover, desative antes.
        </p>

        {creating && <NewUserForm onDone={() => setCreating(false)} />}

        {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {isError && (
          <p className="text-destructive text-[13px]" role="alert">
            {error.message}
          </p>
        )}
        {users && (
          <div className="border-border overflow-x-auto rounded border">
            <table className="w-full text-left">
              <thead>
                <tr className="border-border bg-card border-b text-[11px]">
                  <th className="text-muted-foreground px-4 py-2 font-medium">Usuário</th>
                  <th className="text-muted-foreground px-4 py-2 font-medium">Papel</th>
                  <th className="text-muted-foreground px-4 py-2 font-medium">Situação</th>
                  <th className="px-4 py-2">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <UserRow key={u.id} user={u} isSelf={u.id === me?.id} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
