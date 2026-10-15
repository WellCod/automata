"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import client from "@/lib/api/client";

export type TeamMemberValue = { agent_id: string; version_id: string | null };

interface Props {
  value: TeamMemberValue[];
  onChange: (value: TeamMemberValue[]) => void;
  error?: string;
}

const hintCls = "text-muted-foreground text-[11px]";
const selectCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

export function usePublishedAgents() {
  return useQuery({
    queryKey: ["configs", "published-agents"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs", {
        params: { query: { kind: "agent", status: "published", page_size: 100 } },
      });
      if (res.error) throw new Error("Falha ao carregar agentes");
      return res.data!.items;
    },
  });
}

function PinnedVersion({
  agentId,
  value,
  onChange,
  label,
}: {
  agentId: string;
  value: string | null;
  onChange: (versionId: string | null) => void;
  label: string;
}) {
  const { data: versions } = useQuery({
    queryKey: ["versions", agentId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/versions", {
        params: { path: { config_id: agentId } },
      });
      if (res.error) throw new Error("Falha ao carregar versões");
      return res.data!;
    },
  });
  const published = (versions ?? []).filter((v) => v.status === "published");
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className={selectCls}
      aria-label={`Versão de ${label}`}
    >
      <option value="">Versão vigente</option>
      {published.map((v) => (
        <option key={v.id} value={v.id}>
          Fixar v{v.version_number}
        </option>
      ))}
    </select>
  );
}

export function TeamMembersPicker({ value, onChange, error }: Props) {
  const { data: agents, isPending, isError } = usePublishedAgents();
  const selected = new Map(value.map((m) => [m.agent_id, m]));

  function toggle(agentId: string, checked: boolean) {
    onChange(
      checked
        ? [...value, { agent_id: agentId, version_id: null }]
        : value.filter((m) => m.agent_id !== agentId),
    );
  }

  function pin(agentId: string, versionId: string | null) {
    onChange(value.map((m) => (m.agent_id === agentId ? { ...m, version_id: versionId } : m)));
  }

  return (
    <fieldset className="border-border flex flex-col gap-3 rounded border px-4 pt-3 pb-4">
      <legend className="text-foreground px-1 text-[13px] font-medium">
        Membros<span className="text-destructive ml-0.5">*</span>
      </legend>
      <p className={hintCls}>
        A descrição de cada agente é o que o líder lê para decidir a quem delegar. Só agentes
        publicados entram no time.
      </p>
      {isPending && <p className={hintCls}>Carregando agentes…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Não foi possível carregar os agentes.
        </p>
      )}
      {agents && agents.length === 0 && (
        <p className={hintCls}>
          Nenhum agente publicado.{" "}
          <Link href="/" className="text-accent underline-offset-2 hover:underline">
            Publique um agente
          </Link>{" "}
          antes de montar o time.
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {agents?.map((agent) => {
          const member = selected.get(agent.id);
          return (
            <li
              key={agent.id}
              className="border-border flex items-start justify-between gap-3 rounded border px-3 py-2"
            >
              <label className="flex min-w-0 items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={member !== undefined}
                  onChange={(e) => toggle(agent.id, e.target.checked)}
                />
                <span className="min-w-0">
                  <span className="text-foreground block text-[13px]">{agent.name}</span>
                  <span className={`${hintCls} block`}>{agent.description}</span>
                </span>
              </label>
              {member && (
                <PinnedVersion
                  agentId={agent.id}
                  value={member.version_id}
                  onChange={(v) => pin(agent.id, v)}
                  label={agent.name}
                />
              )}
            </li>
          );
        })}
      </ul>
      {error && (
        <p className="text-destructive text-[11px]" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
