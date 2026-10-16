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
      const res = await client.GET("/api/v1/me");
      if (!res.data) throw new Error("Falha ao carregar o usuário");
      return res.data;
    },
    staleTime: 5 * 60_000,
  });
}

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/users");
      if (!res.data) {
        throw new Error(
          res.response.status === 403
            ? "Só owners gerenciam usuários."
            : "Falha ao carregar usuários",
        );
      }
      return res.data;
    },
  });
}

// Senha temporária que já atende a política da API (12+, maiúscula e dígito)
export function temporaryPassword(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const bytes = new Uint32Array(14);
  crypto.getRandomValues(bytes);
  const body = Array.from(bytes, (n) => alphabet[n % alphabet.length]).join("");
  return `A${body}7`;
}
