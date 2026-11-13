"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";
import { Badge } from "@/components/ui/status-badge";
import client from "@/lib/api/client";
import {
  type Channel,
  CREDENTIAL_FIELDS,
  KIND_LABEL,
  useChannels,
  useSaveChannel,
} from "@/lib/api/channels";
import { apiErrorMessage } from "@/lib/api/errors";

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";
type ChannelKind = "whatsapp" | "slack";

const labelCls = "text-foreground flex flex-col gap-1 text-[12px] font-medium";

// agentes e times publicados: o canal responde com a versão vigente (ou o canário)
function useResponders() {
  return useQuery({
    queryKey: ["configs", "responders"],
    queryFn: async () => {
      const out = [];
      for (const kind of ["agent", "team"] as const) {
        const res = await client.GET("/api/v1/configs", {
          params: { query: { kind, status: "published", page_size: 100 } },
        });
        if (res.error) throw new Error("Falha ao carregar os agentes");
        out.push(...res.data!.items);
      }
      return out;
    },
  });
}

function webhookUrl(channel: Channel): string {
  // o painel é o endereço público; a rota /hooks repassa à API (ADR-0044)
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `${origin}${channel.webhook_path}`;
}

interface FormProps {
  channel: Channel | null;
  onDone: () => void;
}

function ChannelForm({ channel, onDone }: FormProps) {
  const { data: responders = [] } = useResponders();
  const save = useSaveChannel();
  const [kind, setKind] = useState<ChannelKind>(channel?.kind === "slack" ? "slack" : "whatsapp");
  const [name, setName] = useState(channel?.name ?? "");
  const [configId, setConfigId] = useState(channel?.config_id ?? "");
  const [creds, setCreds] = useState<Record<string, string>>({});
  const [handoff, setHandoff] = useState(channel?.handoff_enabled ?? true);
  const [keywords, setKeywords] = useState(
    (channel?.handoff_keywords ?? ["atendente", "humano"]).join(", "),
  );
  const [message, setMessage] = useState(
    channel?.handoff_message ?? "Vou te passar para uma pessoa da equipe. Um momento.",
  );

  function submit() {
    const handoffKeywords = keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    const filled = Object.fromEntries(Object.entries(creds).filter(([, v]) => v.trim()));
    const common = {
      name,
      config_id: configId,
      handoff_enabled: handoff,
      handoff_keywords: handoffKeywords,
      handoff_message: message,
    };
    const args =
      channel === null
        ? ({ id: null, body: { ...common, kind, credentials: filled, enabled: true } } as const)
        : ({
            id: channel.id,
            body: {
              ...common,
              enabled: channel.enabled,
              credentials: Object.keys(filled).length ? filled : null,
            },
          } as const);
    save.mutate(args, {
      onSuccess: () => {
        toast.success(channel ? "Canal salvo" : "Canal criado");
        onDone();
      },
    });
  }

  return (
    <form
      aria-label={channel ? `Editar ${channel.name}` : "Novo canal"}
      className="border-border bg-card flex flex-col gap-3 rounded border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <label className={labelCls}>
          Tipo
          <select
            className={inputCls}
            value={kind}
            disabled={channel !== null}
            onChange={(e) => setKind(e.target.value === "slack" ? "slack" : "whatsapp")}
          >
            <option value="whatsapp">WhatsApp</option>
            <option value="slack">Slack</option>
          </select>
        </label>
        <label className={labelCls}>
          Nome
          <input
            className={inputCls}
            value={name}
            required
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className={labelCls}>
          Quem responde
          <select
            className={inputCls}
            value={configId}
            required
            onChange={(e) => setConfigId(e.target.value)}
          >
            <option value="">Escolha um agente ou time</option>
            {responders.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.kind === "team" ? " (time)" : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-foreground mb-1 text-[12px] font-medium">
          Credencial {channel ? "(vazio mantém a atual)" : ""}
        </legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {CREDENTIAL_FIELDS[kind].map((f) => (
            <label key={f.key} className={labelCls}>
              {f.label}
              <PasswordInput
                className={inputCls}
                value={creds[f.key] ?? ""}
                required={channel === null}
                autoComplete="off"
                onChange={(e) => setCreds((c) => ({ ...c, [f.key]: e.target.value }))}
              />
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-foreground mb-1 text-[12px] font-medium">
          Passagem para atendente
        </legend>
        <label className="text-foreground flex items-center gap-2 text-[12px]">
          <input type="checkbox" checked={handoff} onChange={(e) => setHandoff(e.target.checked)} />
          O cliente ou o agente podem pedir uma pessoa
        </label>
        {handoff && (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={labelCls}>
              Palavras do cliente, separadas por vírgula
              <input
                className={inputCls}
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
              />
            </label>
            <label className={labelCls}>
              Mensagem ao passar
              <input
                className={inputCls}
                value={message}
                maxLength={500}
                onChange={(e) => setMessage(e.target.value)}
              />
            </label>
          </div>
        )}
      </fieldset>

      {save.error && <p className="text-destructive text-[12px]">{save.error.message}</p>}
      <div className="flex justify-end gap-2">
        <Button size="sm" type="button" onClick={onDone}>
          Cancelar
        </Button>
        <Button size="sm" variant="accent" type="submit" disabled={save.isPending}>
          {save.isPending ? "Salvando…" : "Salvar canal"}
        </Button>
      </div>
    </form>
  );
}

function ChannelRow({ channel, onEdit }: { channel: Channel; onEdit: () => void }) {
  const queryClient = useQueryClient();
  const save = useSaveChannel();
  const [confirm, setConfirm] = useState(false);
  const test = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/channels/{channel_id}/test", {
        params: { path: { channel_id: channel.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha no teste"));
      return res.data!;
    },
    onSuccess: (r) => (r.ok ? toast.success(r.detail) : toast.error(r.detail)),
    onError: (e) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/channels/{channel_id}", {
        params: { path: { channel_id: channel.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao apagar"));
    },
    onSuccess: () => {
      toast.success("Canal apagado");
      void queryClient.invalidateQueries({ queryKey: ["channels"] });
    },
  });

  function toggle() {
    save.mutate({
      id: channel.id,
      body: {
        name: channel.name,
        config_id: channel.config_id,
        enabled: !channel.enabled,
        handoff_enabled: channel.handoff_enabled,
        handoff_keywords: channel.handoff_keywords,
        handoff_message: channel.handoff_message,
        credentials: null,
      },
    });
  }

  return (
    <li className="border-border flex flex-col gap-2 border-t py-3 text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-foreground font-medium">{channel.name}</span>
        <Badge tone="neutral">{KIND_LABEL[channel.kind] ?? channel.kind}</Badge>
        <Badge tone={channel.enabled ? "active" : "pending"}>
          {channel.enabled ? "Ligado" : "Desligado"}
        </Badge>
        <span className="text-muted-foreground">responde: {channel.config_name}</span>
      </div>
      <p className="text-muted-foreground text-[12px] break-all">
        Webhook: <code className="text-foreground">{webhookUrl(channel)}</code>
      </p>
      <div className="flex flex-wrap gap-2">
        <Button size="xs" onClick={() => test.mutate()} disabled={test.isPending}>
          {test.isPending ? "Testando…" : "Testar credencial"}
        </Button>
        <Button size="xs" onClick={onEdit}>
          Editar
        </Button>
        <Button size="xs" onClick={toggle} disabled={save.isPending}>
          {channel.enabled ? "Desligar" : "Ligar"}
        </Button>
        {confirm ? (
          <>
            <Button size="xs" variant="destructive" onClick={() => remove.mutate()}>
              Apagar canal e conversas
            </Button>
            <Button size="xs" variant="muted" onClick={() => setConfirm(false)}>
              Manter
            </Button>
          </>
        ) : (
          <Button size="xs" variant="subtleDestructive" onClick={() => setConfirm(true)}>
            Apagar
          </Button>
        )}
      </div>
    </li>
  );
}

export default function ChannelsPage() {
  const { data: channels = [], isLoading, error } = useChannels();
  const [editing, setEditing] = useState<Channel | "new" | null>(null);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center justify-between border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Canais</h1>
        {editing === null && (
          <Button size="sm" variant="accent" onClick={() => setEditing("new")}>
            <Plus aria-hidden />
            Novo canal
          </Button>
        )}
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Um canal liga um agente ou time a um número de WhatsApp ou a um app de Slack. Cadastre no
          provedor o endereço do webhook mostrado aqui; a credencial fica cifrada e não volta para a
          tela. Só owners veem esta página.
        </p>
        {editing !== null && (
          <ChannelForm
            key={editing === "new" ? "new" : editing.id}
            channel={editing === "new" ? null : editing}
            onDone={() => setEditing(null)}
          />
        )}
        {isLoading && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {error && <p className="text-destructive text-[13px]">{error.message}</p>}
        {!isLoading && !error && channels.length === 0 && editing === null && (
          <p className="text-muted-foreground text-[13px]">Nenhum canal ainda.</p>
        )}
        {channels.length > 0 && (
          <ul aria-label="Canais">
            {channels.map((c) => (
              <ChannelRow key={c.id} channel={c} onEdit={() => setEditing(c)} />
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
