"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useId } from "react";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

export type McpServer = components["schemas"]["McpServerResponse"];
export type McpBinding = {
  server_id: string;
  tools: string[] | null;
  require_confirmation: string[];
};

interface Props {
  value: McpBinding[];
  onChange: (value: McpBinding[]) => void;
}

export function useMcpServers() {
  return useQuery({
    queryKey: ["mcp-servers"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/mcp-servers");
      if (res.error) throw new Error("Falha ao carregar servidores MCP");
      return res.data!;
    },
  });
}

const labelCls = "text-foreground text-[13px]";
const hintCls = "text-muted-foreground text-[11px]";

function ServerBinding({
  server,
  binding,
  onChange,
}: {
  server: McpServer;
  binding: McpBinding | undefined;
  onChange: (binding: McpBinding | undefined) => void;
}) {
  const baseId = useId();
  const tools = server.tools ?? [];
  const enabled = binding !== undefined;
  const allTools = binding?.tools === null;
  const selected = new Set(binding?.tools ?? []);
  const confirm = new Set(binding?.require_confirmation ?? []);
  const liberadas = allTools ? tools.map((t) => t.name) : [...selected];

  function update(patch: Partial<McpBinding>) {
    if (!binding) return;
    onChange({ ...binding, ...patch });
  }

  function toggleTool(name: string, checked: boolean) {
    const next = new Set(selected);
    if (checked) next.add(name);
    else next.delete(name);
    update({
      tools: [...next],
      // confirmação só vale para tool liberada
      require_confirmation: binding!.require_confirmation.filter((t) => next.has(t)),
    });
  }

  function toggleConfirm(name: string, checked: boolean) {
    const next = new Set(confirm);
    if (checked) next.add(name);
    else next.delete(name);
    update({ require_confirmation: [...next] });
  }

  return (
    <div className="border-border flex flex-col gap-2 rounded border px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={`${baseId}-use`} className="flex items-center gap-2">
          <input
            id={`${baseId}-use`}
            type="checkbox"
            checked={enabled}
            onChange={(e) =>
              onChange(
                e.target.checked
                  ? { server_id: server.id, tools: null, require_confirmation: [] }
                  : undefined,
              )
            }
          />
          <span className={labelCls}>{server.name}</span>
        </label>
        <span className={hintCls}>
          prefixo <code>{server.slug}_</code>
        </span>
      </div>

      {enabled && (
        <div className="flex flex-col gap-2 pl-6">
          {server.tools === null ? (
            <p className={hintCls}>
              Tools ainda não descobertas: o agente usa todas as do servidor.{" "}
              <Link href="/mcp" className="text-accent underline-offset-2 hover:underline">
                Testar conexão
              </Link>{" "}
              para escolher.
            </p>
          ) : (
            <>
              <fieldset className="flex gap-4">
                <legend className="sr-only">Quais tools de {server.name}</legend>
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    name={`${baseId}-mode`}
                    checked={allTools}
                    onChange={() => update({ tools: null })}
                  />
                  <span className={labelCls}>Todas</span>
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    name={`${baseId}-mode`}
                    checked={!allTools}
                    onChange={() =>
                      update({
                        tools: tools.map((t) => t.name),
                      })
                    }
                  />
                  <span className={labelCls}>Escolher</span>
                </label>
              </fieldset>

              <ul className="flex flex-col gap-1.5" aria-label={`Tools de ${server.name}`}>
                {tools.map((tool) => {
                  const liberada = liberadas.includes(tool.name);
                  return (
                    <li key={tool.name} className="flex items-start justify-between gap-3">
                      <label className="flex min-w-0 items-start gap-2">
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={liberada}
                          disabled={allTools}
                          onChange={(e) => toggleTool(tool.name, e.target.checked)}
                          aria-label={`Liberar ${tool.name}`}
                        />
                        <span className="min-w-0">
                          <code className="text-foreground text-[12px]">{tool.name}</code>
                          {tool.description && (
                            <span className={`${hintCls} block`}>{tool.description}</span>
                          )}
                        </span>
                      </label>
                      <label className="flex flex-none items-center gap-1.5">
                        <input
                          type="checkbox"
                          checked={confirm.has(tool.name)}
                          disabled={!liberada}
                          onChange={(e) => toggleConfirm(tool.name, e.target.checked)}
                          aria-label={`Pedir confirmação antes de ${tool.name}`}
                        />
                        <span className={hintCls}>confirmar</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function McpToolsSelector({ value, onChange }: Props) {
  const { data: servers, isPending, isError } = useMcpServers();

  function setBinding(serverId: string, binding: McpBinding | undefined) {
    const rest = value.filter((b) => b.server_id !== serverId);
    onChange(binding ? [...rest, binding] : rest);
  }

  return (
    <fieldset className="border-border flex flex-col gap-3 rounded border px-4 pt-3 pb-4">
      <legend className="text-foreground px-1 text-[13px] font-medium">Ferramentas (MCP)</legend>
      {isPending && <p className={hintCls}>Carregando servidores…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Não foi possível carregar os servidores MCP.
        </p>
      )}
      {servers && servers.length === 0 && (
        <p className={hintCls}>
          Nenhum servidor MCP cadastrado.{" "}
          <Link href="/mcp" className="text-accent underline-offset-2 hover:underline">
            Cadastrar servidor
          </Link>
        </p>
      )}
      {servers?.map((server) => (
        <ServerBinding
          key={server.id}
          server={server}
          binding={value.find((b) => b.server_id === server.id)}
          onChange={(binding) => setBinding(server.id, binding)}
        />
      ))}
      {servers && (
        <p className={hintCls}>
          Tools marcadas com &quot;confirmar&quot; pausam a execução até alguém aprovar.
        </p>
      )}
    </fieldset>
  );
}
