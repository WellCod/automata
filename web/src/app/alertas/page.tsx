"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { ALERT_EVENTS, type AlertEvent, EVENT_LABELS } from "@/lib/alert-events";
import type { components } from "@/lib/api/schema.d.ts";

type Destination = components["schemas"]["AlertDestinationResponse"];
type Issued = components["schemas"]["AlertDestinationIssued"];

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function when(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function EventPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: AlertEvent[];
  onChange: (next: AlertEvent[]) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-x-4 gap-y-1">
      {ALERT_EVENTS.map((event) => (
        <label key={event} className="text-foreground flex items-center gap-1.5 text-[12px]">
          <input
            type="checkbox"
            checked={value.includes(event)}
            onChange={(e) =>
              onChange(e.target.checked ? [...value, event] : value.filter((v) => v !== event))
            }
          />
          {EVENT_LABELS[event]}
        </label>
      ))}
    </div>
  );
}

function DestinationRow({ dest }: { dest: Destination }) {
  const queryClient = useQueryClient();
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["alert-destinations"] });
  const path = { params: { path: { destination_id: dest.id } } };

  const update = useMutation({
    mutationFn: async (events: AlertEvent[]) => {
      const res = await client.PUT("/api/v1/alert-destinations/{destination_id}", {
        ...path,
        body: { name: dest.name, events },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar os eventos"));
    },
    onSuccess: refresh,
  });
  const test = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/alert-destinations/{destination_id}/test", path);
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao testar o destino"));
    },
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/alert-destinations/{destination_id}", path);
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover o destino"));
    },
    onSuccess: refresh,
  });
  const error = update.error ?? test.error ?? remove.error;

  return (
    <li className="border-border flex flex-col gap-2 border-b py-3 last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-foreground text-[13px] font-medium">{dest.name}</p>
          <p className="text-muted-foreground text-[11px]">
            <code>{dest.host}</code> · criado por {dest.created_by}
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="xs" variant="muted" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? "Enviando…" : "Enviar teste"}
          </Button>
          <Button
            size="xs"
            variant="muted"
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm(`Remover o destino ${dest.name}?`)) remove.mutate();
            }}
          >
            Remover
          </Button>
        </div>
      </div>
      <EventPicker
        label={`Eventos de ${dest.name}`}
        value={dest.events}
        onChange={(next) => {
          if (next.length) update.mutate(next);
        }}
      />
      {dest.last_status && (
        <p
          className={`text-[11px] ${dest.last_status.startsWith("HTTP 2") ? "text-muted-foreground" : "text-destructive"}`}
        >
          Último envio: {dest.last_status}
          {dest.last_at && ` · ${when(dest.last_at)}`}
        </p>
      )}
      {error && (
        <p className="text-destructive text-[12px]" role="alert">
          {error.message}
        </p>
      )}
    </li>
  );
}

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<AlertEvent[]>(["budget.warning", "budget.exceeded"]);
  const [issued, setIssued] = useState<Issued | null>(null);

  const { data, isPending, isError } = useQuery<Destination[]>({
    queryKey: ["alert-destinations"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/alert-destinations");
      if (res.error) throw new Error("Falha ao carregar os destinos");
      return res.data!;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/alert-destinations", {
        body: { name: name.trim(), url: url.trim(), events },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao cadastrar o destino"));
      return res.data!;
    },
    onSuccess: (saved) => {
      setIssued(saved);
      setName("");
      setUrl("");
      void queryClient.invalidateQueries({ queryKey: ["alert-destinations"] });
    },
  });
  const canCreate = name.trim() && url.trim() && events.length > 0 && !create.isPending;

  return (
    <div className="flex max-w-3xl flex-col gap-4 p-6">
      <div>
        <h1 className="text-foreground flex items-center gap-2 text-[18px] font-semibold">
          <Bell className="h-4 w-4" /> Alertas
        </h1>
        <p className="text-muted-foreground text-[13px]">
          Webhooks da instância que recebem avisos de todos os agentes, times e workflows: orçamento
          do mês, pico de erro e mudanças de estado das suítes agendadas. Cola direto em webhook de
          entrada do Slack, Teams ou Discord.
        </p>
      </div>

      <form
        aria-label="Novo destino"
        className="border-border bg-card flex flex-col gap-2 rounded border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (canCreate) create.mutate();
        }}
      >
        <label className="text-muted-foreground flex flex-col gap-1 text-[12px]">
          Nome
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="#operacao no Slack"
            className={inputCls}
          />
        </label>
        <label className="text-muted-foreground flex flex-col gap-1 text-[12px]">
          URL do webhook
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://hooks.slack.com/services/…"
            className={inputCls}
          />
        </label>
        <EventPicker label="Eventos do novo destino" value={events} onChange={setEvents} />
        <div>
          <Button size="sm" variant="strong" type="submit" disabled={!canCreate}>
            {create.isPending ? "Cadastrando…" : "Cadastrar destino"}
          </Button>
        </div>
        {create.error && (
          <p className="text-destructive text-[12px]" role="alert">
            {create.error.message}
          </p>
        )}
      </form>

      {issued && (
        <div
          role="alertdialog"
          aria-label="Segredo do destino"
          className="flex flex-col gap-1 rounded border border-amber-500/50 p-3 text-[12px]"
        >
          <p className="text-foreground">
            Guarde o segredo de {issued.name}: ele não será mostrado de novo. Cada aviso leva{" "}
            <code>X-Automata-Signature: sha256=…</code>, o HMAC do corpo com este segredo.
          </p>
          <code className="border-border bg-muted rounded border p-1 break-all">
            {issued.secret}
          </code>
          <div>
            <Button size="xs" variant="muted" onClick={() => setIssued(null)}>
              Já guardei
            </Button>
          </div>
        </div>
      )}

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]">
          Falha ao carregar os destinos. Só o owner da instância gerencia alertas.
        </p>
      )}
      {data && data.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhum destino cadastrado.</p>
      )}
      {data && data.length > 0 && (
        <ul aria-label="Destinos" className="border-border bg-card rounded border px-3">
          {data.map((dest) => (
            <DestinationRow key={dest.id} dest={dest} />
          ))}
        </ul>
      )}
    </div>
  );
}
