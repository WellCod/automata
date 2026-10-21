"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { EvalSchedule } from "@/lib/eval-checks";
import { Button } from "@/components/ui/button";

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function when(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function EvalWebhook({ configId, schedule }: { configId: string; schedule: EvalSchedule }) {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  // segredo devolvido uma vez só pela API; some ao fechar
  const [secret, setSecret] = useState<string | null>(null);
  const path = { params: { path: { config_id: configId } } };
  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: ["eval-schedule", configId] });

  const save = useMutation({
    mutationFn: async () => {
      const res = await client.PUT("/api/v1/configs/{config_id}/eval-schedule/webhook", {
        ...path,
        body: { url: url.trim() },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o webhook"));
      return res.data!;
    },
    onSuccess: (issued) => {
      setSecret(issued.secret);
      setUrl("");
      refresh();
    },
  });
  const test = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/configs/{config_id}/eval-schedule/webhook/test", path);
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao testar o webhook"));
      return res.data!;
    },
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/configs/{config_id}/eval-schedule/webhook", path);
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover o webhook"));
    },
    onSuccess: () => {
      setSecret(null);
      refresh();
    },
  });
  const error = save.error ?? test.error ?? remove.error;

  return (
    <div aria-label="Aviso por webhook" role="group" className="flex flex-col gap-1.5">
      <p className="text-foreground text-[12px] font-medium">Aviso por webhook</p>
      <p className="text-muted-foreground text-[11px]">
        Avisa quando a suíte agendada regride, passa a falhar ou volta a passar. Cola direto em
        webhook de entrada do Slack, Teams ou Discord.
      </p>
      {schedule.webhook_host ? (
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          <span className="text-foreground">
            Avisando em <code>{schedule.webhook_host}</code>
          </span>
          <Button size="xs" variant="muted" disabled={test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? "Enviando…" : "Enviar teste"}
          </Button>
          <Button
            size="xs"
            variant="muted"
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            Remover webhook
          </Button>
        </div>
      ) : null}
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) save.mutate();
        }}
      >
        <input
          aria-label="URL do webhook"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://hooks.slack.com/services/…"
          className={`${inputCls} min-w-64 flex-1`}
        />
        <Button size="xs" variant="strong" type="submit" disabled={!url.trim() || save.isPending}>
          {schedule.webhook_host ? "Trocar webhook" : "Salvar webhook"}
        </Button>
      </form>
      {secret && (
        <div
          role="alertdialog"
          aria-label="Segredo do webhook"
          className="flex flex-col gap-1 rounded border border-amber-500/50 p-2 text-[12px]"
        >
          <p className="text-foreground">
            Guarde o segredo: ele não será mostrado de novo. Cada aviso leva{" "}
            <code>X-Automata-Signature: sha256=…</code>, o HMAC do corpo com este segredo.
          </p>
          <code className="border-border bg-muted rounded border p-1 break-all">{secret}</code>
          <div>
            <Button size="xs" variant="muted" onClick={() => setSecret(null)}>
              Já guardei
            </Button>
          </div>
        </div>
      )}
      {schedule.webhook_last_status && (
        <p
          className={`text-[11px] ${schedule.webhook_last_status.startsWith("HTTP 2") ? "text-muted-foreground" : "text-destructive"}`}
          role="status"
        >
          Último envio: {schedule.webhook_last_status}
          {schedule.webhook_last_at && ` · ${when(schedule.webhook_last_at)}`}
        </p>
      )}
      {error && (
        <p className="text-destructive text-[12px]" role="alert">
          {error.message}
        </p>
      )}
    </div>
  );
}
