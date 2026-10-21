"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";
import { Badge, type BadgeTone } from "@/components/ui/status-badge";
import client from "@/lib/api/client";
import {
  type Connector,
  type ConnectorKind,
  type ConnectorTest,
  KIND_LABEL,
  origin,
  SECRET_FIELDS,
  SETTINGS_FIELDS,
  summaryText,
  useConnectors,
} from "@/lib/api/connectors";
import { apiErrorMessage } from "@/lib/api/errors";
import { useMe } from "@/lib/api/users";

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

const STATUS: Record<string, { tone: BadgeTone; label: string }> = {
  idle: { tone: "neutral", label: "nunca sincronizado" },
  running: { tone: "pending", label: "sincronizando" },
  ok: { tone: "active", label: "sincronizado" },
  failed: { tone: "danger", label: "falhou" },
};

function when(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function ConnectorForm({
  baseId,
  initial,
  onDone,
}: {
  baseId: string;
  initial?: Connector;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<ConnectorKind>(initial?.kind ?? "github");
  const [name, setName] = useState(initial?.name ?? "");
  const [settings, setSettings] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(initial?.settings ?? {}).map(([k, v]) => [k, v == null ? "" : String(v)]),
    ),
  );
  const [secret, setSecret] = useState<Record<string, string>>({});
  const [hours, setHours] = useState(
    initial?.sync_every_hours ? String(initial.sync_every_hours) : "",
  );

  const save = useMutation({
    mutationFn: async () => {
      // campo vazio não vai: a API aplica o padrão (branch main, AWS, pasta raiz)
      const cleaned = Object.fromEntries(
        SETTINGS_FIELDS[kind]
          .map((f) => [f.key, settings[f.key]?.trim() ?? ""])
          .filter(([, v]) => v !== ""),
      );
      const typed = Object.values(secret).some((v) => v.trim());
      const body = {
        kind,
        name: name.trim(),
        settings: cleaned,
        // na edição, segredo em branco mantém o salvo
        secret: typed || !initial ? secret : null,
        sync_every_hours: hours ? Number(hours) : null,
      };
      const res = initial
        ? await client.PUT("/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}", {
            params: { path: { base_id: baseId, connector_id: initial.id } },
            body,
          })
        : await client.POST("/api/v1/knowledge-bases/{base_id}/connectors", {
            params: { path: { base_id: baseId } },
            body,
          });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o conector"));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases", baseId, "connectors"] });
      onDone();
    },
  });

  return (
    <form
      aria-label={initial ? `Editar ${initial.name}` : "Novo conector"}
      className="border-border bg-card flex flex-col gap-2 rounded border p-3"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="flex flex-wrap gap-2">
        <select
          aria-label="Origem"
          value={kind}
          disabled={!!initial}
          onChange={(e) => {
            setKind(e.target.value as ConnectorKind);
            setSettings({});
            setSecret({});
          }}
          className={`${inputCls} w-auto`}
        >
          {(Object.keys(KIND_LABEL) as ConnectorKind[]).map((k) => (
            <option key={k} value={k}>
              {KIND_LABEL[k]}
            </option>
          ))}
        </select>
        <input
          aria-label="Nome do conector"
          required
          value={name}
          maxLength={255}
          placeholder="Documentação do produto"
          onChange={(e) => setName(e.target.value)}
          className={`${inputCls} flex-1`}
        />
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {SETTINGS_FIELDS[kind].map((f) => (
          <label key={f.key} className="text-muted-foreground flex flex-col gap-1 text-[12px]">
            {f.label}
            <input
              required={f.required}
              value={settings[f.key] ?? ""}
              placeholder={f.placeholder}
              onChange={(e) => setSettings({ ...settings, [f.key]: e.target.value })}
              className={inputCls}
            />
          </label>
        ))}
        {SECRET_FIELDS[kind].map((f) => (
          <label key={f.key} className="text-muted-foreground flex flex-col gap-1 text-[12px]">
            {f.label}
            <PasswordInput
              aria-label={f.label}
              required={f.required && !initial?.has_secret}
              value={secret[f.key] ?? ""}
              autoComplete="off"
              placeholder={initial?.has_secret ? "configurado; vazio mantém" : undefined}
              onChange={(e) => setSecret({ ...secret, [f.key]: e.target.value })}
              className={inputCls}
            />
          </label>
        ))}
        <label className="text-muted-foreground flex flex-col gap-1 text-[12px]">
          Sincronizar a cada (horas)
          <input
            type="number"
            min={1}
            max={168}
            value={hours}
            placeholder="vazio = só manual"
            onChange={(e) => setHours(e.target.value)}
            className={inputCls}
          />
        </label>
      </div>
      <p className="text-muted-foreground text-[11px]">
        Use uma credencial só de leitura, restrita ao repositório, bucket ou pasta: a base recebe
        tudo o que ela lê dentro do caminho. O segredo fica cifrado e não é mostrado de novo.
      </p>
      {save.isError && (
        <p className="text-destructive text-[12px]" role="alert">
          {save.error.message}
        </p>
      )}
      <div className="flex gap-2">
        <Button size="sm" variant="strong" type="submit" disabled={save.isPending}>
          {save.isPending ? "Salvando…" : "Salvar conector"}
        </Button>
        <Button size="sm" variant="muted" type="button" onClick={onDone}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}

function ConnectorRow({
  baseId,
  connector,
  canManage,
}: {
  baseId: string;
  connector: Connector;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [tested, setTested] = useState<ConnectorTest | null>(null);
  const path = { params: { path: { base_id: baseId, connector_id: connector.id } } };
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["knowledge-bases", baseId, "connectors"] });
    void queryClient.invalidateQueries({ queryKey: ["knowledge-bases", baseId, "contents"] });
  };

  const test = useMutation({
    mutationFn: async () => {
      const res = await client.POST(
        "/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}/test",
        path,
      );
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao testar"));
      return res.data!;
    },
    onSuccess: setTested,
  });
  const sync = useMutation({
    mutationFn: async () => {
      const res = await client.POST(
        "/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}/sync",
        path,
      );
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao sincronizar"));
    },
    onSuccess: refresh,
    onError: (e) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE(
        "/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}",
        path,
      );
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover"));
    },
    onSuccess: () => {
      toast.success(`${connector.name} removido, com os documentos dele`);
      refresh();
    },
    onError: (e) => toast.error(e.message),
  });

  if (editing) {
    return (
      <li>
        <ConnectorForm baseId={baseId} initial={connector} onDone={() => setEditing(false)} />
      </li>
    );
  }
  const status = STATUS[connector.last_status] ?? STATUS.idle;
  const running = connector.last_status === "running";
  return (
    <li
      aria-label={`Conector ${connector.name}`}
      className="border-border bg-card flex flex-col gap-1.5 rounded border px-3 py-2"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-foreground truncate text-[13px] font-medium">{connector.name}</span>
          <Badge tone="neutral">{KIND_LABEL[connector.kind]}</Badge>
          <Badge tone={status.tone}>{status.label}</Badge>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button size="xs" variant="muted" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? "Testando…" : "Testar"}
          </Button>
          <Button
            size="xs"
            variant="strong"
            disabled={running || sync.isPending}
            onClick={() => sync.mutate()}
          >
            Sincronizar
          </Button>
          {canManage && (
            <Button size="xs" variant="muted" onClick={() => setEditing(true)}>
              Editar
            </Button>
          )}
          {canManage &&
            (confirm ? (
              <>
                <Button size="xs" variant="destructive" onClick={() => remove.mutate()}>
                  Confirmar
                </Button>
                <Button size="xs" variant="muted" onClick={() => setConfirm(false)}>
                  Manter
                </Button>
              </>
            ) : (
              <Button size="xs" variant="subtleDestructive" onClick={() => setConfirm(true)}>
                Remover
              </Button>
            ))}
        </div>
      </div>
      <p className="text-muted-foreground truncate text-[11px]">
        <code>{origin(connector)}</code> · {connector.content_count} documento(s)
        {connector.sync_every_hours
          ? ` · a cada ${connector.sync_every_hours} h, próxima ${when(connector.next_sync_at)}`
          : " · só manual"}
      </p>
      {connector.last_sync_at && (
        <p className="text-muted-foreground text-[11px]">
          Última: {when(connector.last_sync_at)} · {summaryText(connector.last_summary)}
        </p>
      )}
      {connector.last_message && (
        <p className="text-destructive text-[11px]" role="alert">
          {connector.last_message}
        </p>
      )}
      {tested && (
        <p className={`text-[11px] ${tested.ok ? "text-muted-foreground" : "text-destructive"}`}>
          {tested.ok
            ? `Conexão ok: ${tested.files} arquivo(s) entrariam${
                tested.sample.length ? ` (${tested.sample.join(", ")}…)` : ""
              }`
            : `Falhou: ${tested.error}`}
        </p>
      )}
    </li>
  );
}

export function KnowledgeConnectors({ baseId }: { baseId: string }) {
  const { data, isPending, isError } = useConnectors(baseId);
  const { data: me } = useMe();
  const [creating, setCreating] = useState(false);
  // credencial de conector é do owner; o editor sincroniza (ADR-0024)
  const canManage = me?.role === "owner";

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground text-[13px]">
        Conecte um repositório do GitHub, um bucket S3 ou uma pasta do SharePoint. A sincronização
        compara pela versão de cada arquivo: novo entra, alterado é reindexado, removido sai da
        base.
      </p>
      {canManage && !creating && (
        <div>
          <Button size="sm" onClick={() => setCreating(true)}>
            Novo conector
          </Button>
        </div>
      )}
      {creating && <ConnectorForm baseId={baseId} onDone={() => setCreating(false)} />}
      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Não foi possível carregar os conectores.
        </p>
      )}
      {data && data.length === 0 && !creating && (
        <p className="text-muted-foreground text-[13px]">
          Nenhum conector.{!canManage && " Só o owner da instância cadastra."}
        </p>
      )}
      {data && data.length > 0 && (
        <ul className="flex flex-col gap-1.5" aria-label="Conectores">
          {data.map((c) => (
            <ConnectorRow key={c.id} baseId={baseId} connector={c} canManage={canManage} />
          ))}
        </ul>
      )}
    </div>
  );
}
