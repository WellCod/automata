"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

export type KeyRotationStatus = components["schemas"]["KeyRotationStatus"];

export const SECRET_TABLES: Record<string, string> = {
  mcp_server: "Servidores MCP",
  eval_schedule: "Webhooks da suíte",
  alert_destination: "Destinos de alerta",
  knowledge_connector: "Conectores de conhecimento",
};

export function useKeyRotation() {
  return useQuery({
    queryKey: ["key-rotation"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/key-rotation");
      if (res.error)
        throw new Error("Falha ao carregar o estado das chaves. Apenas owners têm acesso.");
      return res.data!;
    },
  });
}

function Row({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1 text-[13px]">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={warn ? "font-medium text-amber-600 dark:text-amber-400" : "text-foreground"}>
        {value}
      </dd>
    </div>
  );
}

export function KeyRotationView({ status }: { status: KeyRotationStatus }) {
  const { jwt, secrets } = status;
  const outside = jwt.tokens_on_previous + jwt.tokens_without_kid;
  const pending = Object.values(secrets.pending).some((n) => n > 0);
  const previousSet = jwt.previous_kid !== null || secrets.previous_configured;

  return (
    <div className="flex flex-col gap-4">
      <p
        role="status"
        className={`text-foreground rounded border px-4 py-3 text-[13px] ${status.done ? "border-border" : "border-amber-500/50"}`}
      >
        {status.done
          ? previousSet
            ? "Nada depende mais das chaves anteriores. Tire JWT_PREVIOUS_PUBLIC_KEY e MCP_SECRETS_PREVIOUS_KEY do ambiente da API e do painel."
            : "Nenhuma troca em andamento."
          : "Troca em andamento: ainda há tokens ou segredos que dependem das chaves anteriores."}
      </p>

      <section aria-labelledby="jwt-title" className="border-border rounded border px-4 py-3">
        <h2 id="jwt-title" className="text-foreground mb-1 text-sm font-medium">
          Chave JWT
        </h2>
        <dl>
          <Row label="kid atual" value={jwt.current_kid ?? "chave inválida"} />
          <Row label="kid anterior" value={jwt.previous_kid ?? "nenhuma configurada"} />
          <Row
            label="Tokens de integração na chave anterior"
            value={String(jwt.tokens_on_previous)}
            warn={jwt.tokens_on_previous > 0}
          />
          <Row
            label="Tokens de integração de antes do kid"
            value={String(jwt.tokens_without_kid)}
            warn={jwt.tokens_without_kid > 0}
          />
        </dl>
        {outside > 0 && (
          <p className="text-muted-foreground mt-2 text-[13px]">
            Emita um token novo para cada sistema marcado com &quot;chave anterior&quot; em{" "}
            <Link href="/integracoes" className="text-accent underline">
              Integrações
            </Link>{" "}
            e revogue o antigo depois que o sistema trocar.
          </p>
        )}
      </section>

      <section aria-labelledby="secrets-title" className="border-border rounded border px-4 py-3">
        <h2 id="secrets-title" className="text-foreground mb-1 text-sm font-medium">
          Chave dos segredos
        </h2>
        {!secrets.configured ? (
          <p className="text-muted-foreground text-[13px]">
            MCP_SECRETS_KEY não está configurada: nenhum segredo cifrado.
          </p>
        ) : (
          <>
            <dl>
              <Row
                label="Chave anterior"
                value={secrets.previous_configured ? "configurada" : "nenhuma configurada"}
              />
              {Object.entries(SECRET_TABLES).map(([table, label]) => {
                const n = secrets.pending[table] ?? 0;
                return (
                  <Row
                    key={table}
                    label={`${label} na chave anterior`}
                    value={String(n)}
                    warn={n > 0}
                  />
                );
              })}
            </dl>
            {pending && (
              <p className="text-muted-foreground mt-2 text-[13px]">
                Rode <code className="text-foreground">python -m app.rotate_secrets</code> no
                container da API para recifrar com a chave atual.
              </p>
            )}
          </>
        )}
      </section>

      <p className="text-muted-foreground text-[11px]">
        Passo a passo da troca em docs/rotacao-de-chaves.md (ADR-0026).
      </p>
    </div>
  );
}

export function KeyRotationPanel() {
  const { data, isPending, isError, error } = useKeyRotation();
  if (isPending) return <p className="text-muted-foreground text-[13px]">Carregando…</p>;
  if (isError)
    return (
      <p className="text-destructive text-[13px]" role="alert">
        {error.message}
      </p>
    );
  return <KeyRotationView status={data} />;
}
