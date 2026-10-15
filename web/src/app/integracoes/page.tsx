"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { useId, useState } from "react";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { mcpSnippet } from "@/lib/mcp-snippet";
import type { components } from "@/lib/api/schema.d.ts";

type Integration = components["schemas"]["IntegrationResponse"];
type Issued = components["schemas"]["IssuedIntegration"];

const btnCls =
  "inline-flex h-7 items-center rounded border px-3 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40";
const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function usePublished(kind: "agent" | "team") {
  return useQuery({
    queryKey: ["configs", "published", kind],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs", {
        params: { query: { kind, status: "published", page_size: 100 } },
      });
      if (res.error) throw new Error("Falha ao carregar");
      return res.data!.items;
    },
  });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}

function IssuedToken({ issued, onClose }: { issued: Issued; onClose: () => void }) {
  const [copied, setCopied] = useState<string | null>(null);
  const snippet = mcpSnippet(issued.mcp_url, issued.token);

  async function copy(label: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopied(label);
  }

  return (
    <div
      role="alertdialog"
      aria-label="Token emitido"
      className="flex flex-col gap-3 rounded border border-amber-400/60 p-4"
    >
      <p className="text-foreground text-sm font-medium">
        Copie o token agora: ele não será mostrado de novo
      </p>
      <code className="border-border bg-muted text-foreground block overflow-x-auto rounded border p-2 text-[12px] break-all">
        {issued.token}
      </code>
      <p className="text-muted-foreground text-[13px]">
        Configuração para clientes MCP (Claude Desktop, Cursor):
      </p>
      <pre className="border-border bg-muted text-foreground overflow-x-auto rounded border p-2 text-[12px]">
        {snippet}
      </pre>
      {!issued.mcp_url && (
        <p className="text-muted-foreground text-[11px]">
          Defina PUBLIC_BASE_URL na API para o endereço do /mcp sair preenchido.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void copy("token", issued.token)}
          className={`${btnCls} border-foreground text-foreground hover:border-accent hover:text-accent`}
        >
          Copiar token
        </button>
        <button
          type="button"
          onClick={() => void copy("config", snippet)}
          className={`${btnCls} border-border text-foreground hover:border-accent hover:text-accent`}
        >
          Copiar configuração
        </button>
        <button
          type="button"
          onClick={onClose}
          className={`${btnCls} border-border text-muted-foreground hover:text-foreground`}
        >
          Já copiei
        </button>
        <span aria-live="polite" className="text-accent text-[11px]">
          {copied === "token" && "Token copiado"}
          {copied === "config" && "Configuração copiada"}
        </span>
      </div>
    </div>
  );
}

function NewIntegration({ onIssued }: { onIssued: (issued: Issued) => void }) {
  const id = useId();
  const queryClient = useQueryClient();
  const { data: agents } = usePublished("agent");
  const { data: teams } = usePublished("team");
  const [name, setName] = useState("");
  const [days, setDays] = useState(30);
  const [agentIds, setAgentIds] = useState<string[]>([]);
  const [teamIds, setTeamIds] = useState<string[]>([]);

  const issue = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/integrations", {
        body: {
          name: name.trim(),
          agent_ids: agentIds,
          team_ids: teamIds,
          expires_in_days: days,
        },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao emitir token"));
      return res.data!;
    },
    onSuccess: (issued) => {
      setName("");
      setAgentIds([]);
      setTeamIds([]);
      void queryClient.invalidateQueries({ queryKey: ["integrations"] });
      onIssued(issued);
    },
  });

  function toggle(list: string[], set: (v: string[]) => void, value: string, on: boolean) {
    set(on ? [...list, value] : list.filter((v) => v !== value));
  }

  const nothingSelected = agentIds.length === 0 && teamIds.length === 0;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        issue.mutate();
      }}
      className="border-border bg-card flex flex-col gap-4 rounded border p-4"
      aria-label="Nova integração"
    >
      <div className="grid gap-4 sm:grid-cols-[1fr_140px]">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-name`} className="text-foreground text-[13px] font-medium">
            Sistema consumidor
          </label>
          <input
            id={`${id}-name`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex.: atendimento-zendesk"
            className={inputCls}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-days`} className="text-foreground text-[13px] font-medium">
            Validade (dias)
          </label>
          <input
            id={`${id}-days`}
            type="number"
            min={1}
            max={90}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className={inputCls}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <fieldset className="flex flex-col gap-1.5">
          <legend className="text-foreground mb-1 text-[13px] font-medium">Agentes</legend>
          {agents?.length === 0 && (
            <p className="text-muted-foreground text-[11px]">Nenhum agente publicado.</p>
          )}
          {agents?.map((a) => (
            <label key={a.id} className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={agentIds.includes(a.id)}
                onChange={(e) => toggle(agentIds, setAgentIds, a.id, e.target.checked)}
              />
              <span className="text-foreground">{a.name}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="flex flex-col gap-1.5">
          <legend className="text-foreground mb-1 text-[13px] font-medium">Times</legend>
          {teams?.length === 0 && (
            <p className="text-muted-foreground text-[11px]">Nenhum time publicado.</p>
          )}
          {teams?.map((t) => (
            <label key={t.id} className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={teamIds.includes(t.id)}
                onChange={(e) => toggle(teamIds, setTeamIds, t.id, e.target.checked)}
              />
              <span className="text-foreground">{t.name}</span>
            </label>
          ))}
        </fieldset>
      </div>

      {issue.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {issue.error.message}
        </p>
      )}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={issue.isPending || !name.trim() || nothingSelected}
          className={`${btnCls} border-foreground text-foreground hover:border-accent hover:text-accent`}
        >
          {issue.isPending ? "Emitindo…" : "Emitir token"}
        </button>
      </div>
    </form>
  );
}

function IntegrationRow({ item, names }: { item: Integration; names: Record<string, string> }) {
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const revoke = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/integrations/{integration_id}", {
        params: { path: { integration_id: item.id } },
      });
      if (res.error) throw new Error("Falha ao revogar");
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["integrations"] }),
  });
  const expired = new Date(item.expires_at) < new Date();
  const status = item.revoked_at ? "revogado" : expired ? "expirado" : "ativo";
  const resources = [...item.agent_ids, ...item.team_ids].map((i) => names[i] ?? i);

  return (
    <li className="border-border bg-card flex flex-wrap items-center justify-between gap-3 rounded border px-4 py-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-foreground text-[13px] font-medium">
          {item.name}{" "}
          <span
            className={`ml-1 text-[11px] tracking-[0.05em] uppercase ${status === "ativo" ? "text-accent" : "text-muted-foreground"}`}
          >
            {status}
          </span>
        </span>
        <span className="text-muted-foreground text-[13px]">
          Pode chamar: {resources.join(", ")}
        </span>
        <span className="text-muted-foreground text-[11px]">
          emitido por {item.created_by} em {formatDate(item.created_at)} · expira em{" "}
          {formatDate(item.expires_at)}
        </span>
      </div>
      {status === "ativo" &&
        (confirm ? (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => revoke.mutate()}
              disabled={revoke.isPending}
              className={`${btnCls} border-destructive text-destructive`}
            >
              Confirmar revogação
            </button>
            <button
              type="button"
              onClick={() => setConfirm(false)}
              className={`${btnCls} border-border text-muted-foreground hover:text-foreground`}
            >
              Manter
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirm(true)}
            className={`${btnCls} border-border text-muted-foreground hover:border-destructive hover:text-destructive`}
          >
            Revogar
          </button>
        ))}
    </li>
  );
}

export default function IntegrationsPage() {
  const [issued, setIssued] = useState<Issued | null>(null);
  const { data: agents } = usePublished("agent");
  const { data: teams } = usePublished("team");
  const names = Object.fromEntries(
    [...(agents ?? []), ...(teams ?? [])].map((c) => [c.id, c.name]),
  );
  const { data, isPending, isError } = useQuery({
    queryKey: ["integrations"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/integrations");
      if (res.error) throw new Error("Falha ao carregar integrações");
      return res.data!;
    },
  });

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Integrações</h1>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Tokens para sistemas externos e assistentes de IA chamarem agentes e times pela API ou
          como ferramentas via MCP. Cada token só enxerga e executa o que foi liberado nele. Só
          owners emitem e revogam.
        </p>

        {issued && <IssuedToken issued={issued} onClose={() => setIssued(null)} />}
        <NewIntegration onIssued={setIssued} />

        {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {isError && (
          <p className="text-destructive text-[13px]" role="alert">
            Não foi possível carregar as integrações. Apenas owners têm acesso.
          </p>
        )}
        {data && data.length === 0 && (
          <div className="border-border flex flex-col items-center gap-2 rounded border border-dashed px-6 py-8 text-center">
            <KeyRound className="text-accent h-5 w-5" aria-hidden />
            <p className="text-foreground text-sm">Nenhuma integração emitida</p>
          </div>
        )}
        {data && data.length > 0 && (
          <ul className="flex flex-col gap-2" aria-label="Integrações">
            {data.map((item) => (
              <IntegrationRow key={item.id} item={item} names={names} />
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
