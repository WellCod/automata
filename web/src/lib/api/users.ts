"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

export type UserAccount = components["schemas"]["UserResponse"];
export type UserRole = components["schemas"]["UserRole"];

export const ROLE_LABELS: Record<UserRole, string> = {
  owner: "Owner",
  editor: "Editor",
  viewer: "Leitor",
};

export const ROLE_HINTS: Record<UserRole, string> = {
  owner: "Tudo, inclusive usuários, servidores MCP e integrações",
  editor: "Edita, publica e testa agentes; alimenta bases de conhecimento",
  viewer: "Só consulta agentes, execuções e métricas",
};

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const result = await client.GET("/api/v1/me");
      if (!result.data) throw new Error("Falha ao carregar o usuário");
      return result.data;
    },
    staleTime: 5 * 60_000,
  });
}

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const result = await client.GET("/api/v1/users");
      if (!result.data) {
        throw new Error(
          result.response.status === 403
            ? "Só owners gerenciam usuários."
            : "Falha ao carregar usuários",
        );
      }
      return result.data;
    },
  });
}

// Senha temporária que já atende a política da API (12+, maiúscula e dígito)
export function temporaryPassword(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const bytes = new Uint32Array(14);
  crypto.getRandomValues(bytes);
  const body = Array.from(bytes, (randomValue) => alphabet[randomValue % alphabet.length]).join("");
  // maiúscula no começo e dígito no fim: o sorteio sozinho podia sair sem um dos dois
  return `A${body}7`;
}

// O painel esconde o que o papel não permite: o botão que a API recusaria nem aparece (UX-06).
// Enquanto o /me carrega, nada é escondido; a API segue conferindo cada chamada
export function useCan(scope: string): boolean {
  const { data: me } = useMe();
  // resposta sem a lista (API antiga): não esconde nada
  if (!me || !Array.isArray(me.scopes)) return true;
  if (me.role === "owner") return true;
  return me.scopes.includes("agent_os:admin") || me.scopes.includes(scope);
}
