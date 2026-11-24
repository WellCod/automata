"use client";

import { useQuery } from "@tanstack/react-query";

export type InstanceInfo = {
  app_name: string;
  app_logo: string | null;
  brl_per_usd: number | null;
};

// marca padrão enquanto a consulta não volta ou quando ela falha
const DEFAULT_INSTANCE: InstanceInfo = { app_name: "automata", app_logo: null, brl_per_usd: null };

export function useInstance(): InstanceInfo {
  const { data } = useQuery({
    queryKey: ["instance"],
    queryFn: async (): Promise<InstanceInfo> => (await fetch("/api/auth/instance")).json(),
    staleTime: 10 * 60_000,
  });
  return data ?? DEFAULT_INSTANCE;
}

// custo em dólar com o equivalente em reais quando a instância tem cotação (UX-08)
export function formatUsd(cost: number | null, brlPerUsd: number | null, digits = 4): string {
  if (cost === null) return "—";
  const usd = cost.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
  });
  if (!brlPerUsd) return usd;
  const brl = (cost * brlPerUsd).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
  });
  return `${usd} (${brl})`;
}
