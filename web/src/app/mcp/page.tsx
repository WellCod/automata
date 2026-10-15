"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plug } from "lucide-react";
import { useState } from "react";
import { McpServerForm, type McpServerBody } from "@/components/mcp-server-form";
import { type McpServer, useMcpServers } from "@/components/mcp-tools-selector";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function ServerCard({ server, onEdit }: { server: McpServer; onEdit: () => void }) {
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const discover = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/mcp-servers/{server_id}/discover", {
        params: { path: { server_id: server.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao conectar"));
      return res.data!;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["mcp-servers"] }),
  });

  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/mcp-servers/{server_id}", {
        params: { path: { server_id: server.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao excluir"));
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["mcp-servers"] }),
  });

  return (
    <li className="border-border bg-card flex flex-col gap-3 rounded border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-foreground text-sm font-medium">{server.name}</span>
          <span className="text-muted-foreground truncate text-[13px]">{server.url}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => discover.mutate()} disabled={discover.isPending}>
            {discover.isPending ? "Conectando…" : "Testar conexão"}
          </Button>
          <Button onClick={onEdit} variant="muted">
            Editar
          </Button>
          {confirmDelete ? (
            <>
              <Button
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
                variant="destructive"
              >
                Confirmar exclusão
              </Button>
              <Button onClick={() => setConfirmDelete(false)} variant="muted">
                Manter
              </Button>
            </>
          ) : (
            <Button onClick={() => setConfirmDelete(true)} variant="subtleDestructive">
              Excluir
            </Button>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-[13px] sm:grid-cols-4">
        <div>
          <dt className="text-[var(--text-label)]">Prefixo</dt>
          <dd className="text-foreground">
            <code>{server.slug}_</code>
          </dd>
        </div>
        <div>
          <dt className="text-[var(--text-label)]">Headers</dt>
          <dd className="text-foreground">
            {server.header_names.length ? server.header_names.join(", ") : "nenhum"}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--text-label)]">Tools</dt>
          <dd className="text-foreground">{server.tools ? server.tools.length : "—"}</dd>
        </div>
        <div>
          <dt className="text-[var(--text-label)]">Última descoberta</dt>
          <dd className="text-foreground">{formatDate(server.tools_discovered_at)}</dd>
        </div>
      </dl>

      <div aria-live="polite">
        {discover.isError && (
          <p className="text-destructive text-[13px]" role="alert">
            {discover.error.message}
          </p>
        )}
        {discover.isSuccess && (
          <p className="text-accent text-[13px]">
            Conectado: {discover.data.tools?.length ?? 0} tools encontradas.
          </p>
        )}
        {remove.isError && (
          <p className="text-destructive text-[13px]" role="alert">
            {remove.error.message}
          </p>
        )}
      </div>

      {server.tools && server.tools.length > 0 && (
        <details>
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-[13px]">
            Ver tools
          </summary>
          <ul className="mt-2 flex flex-col gap-1.5">
            {server.tools.map((tool) => (
              <li key={tool.name} className="text-[13px]">
                <code className="text-foreground">
                  {server.slug}_{tool.name}
                </code>
                {tool.description && (
                  <span className="text-muted-foreground"> — {tool.description}</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

export default function McpServersPage() {
  const queryClient = useQueryClient();
  const { data: servers, isPending, isError } = useMcpServers();
  const [editing, setEditing] = useState<McpServer | "new" | null>(null);

  const save = useMutation({
    mutationFn: async (body: McpServerBody) => {
      const res =
        editing && editing !== "new"
          ? await client.PUT("/api/v1/mcp-servers/{server_id}", {
              params: { path: { server_id: editing.id } },
              body,
            })
          : await client.POST("/api/v1/mcp-servers", { body });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar servidor"));
      return res.data!;
    },
    onSuccess: () => {
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
    },
  });

  function openForm(target: McpServer | "new") {
    save.reset();
    setEditing(target);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center justify-between border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Servidores MCP</h1>
        <Button onClick={() => openForm("new")} variant="accent">
          Novo servidor
        </Button>
      </header>

      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Sistemas externos que os agentes acessam como ferramentas. Só owners cadastram e alteram;
          quem edita agentes pode testar a conexão para atualizar a lista de tools.
        </p>

        {editing && (
          <McpServerForm
            key={editing === "new" ? "new" : editing.id}
            server={editing === "new" ? undefined : editing}
            pending={save.isPending}
            error={save.isError ? save.error.message : undefined}
            onSubmit={(body) => save.mutate(body)}
            onCancel={() => setEditing(null)}
          />
        )}

        {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {isError && (
          <p className="text-destructive text-[13px]" role="alert">
            Não foi possível carregar os servidores.
          </p>
        )}
        {servers && servers.length === 0 && !editing && (
          <div className="border-border flex flex-col items-center gap-3 rounded border border-dashed px-6 py-10 text-center">
            <Plug className="text-accent h-5 w-5" aria-hidden />
            <p className="text-foreground text-sm">Nenhum servidor MCP cadastrado</p>
            <p className="text-muted-foreground max-w-md text-[13px]">
              Cadastre a URL de um servidor MCP (CRM, ERP, base de conhecimento), teste a conexão e
              escolha, em cada agente, quais tools ele pode usar.
            </p>
          </div>
        )}
        {servers && servers.length > 0 && (
          <ul className="flex flex-col gap-3">
            {servers.map((server) => (
              <ServerCard key={server.id} server={server} onEdit={() => openForm(server)} />
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
