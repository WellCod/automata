"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/status-badge";
import {
  type ConversationDetail,
  type ConversationStatus,
  KIND_LABEL,
  useConversation,
  useConversationAction,
  useConversations,
} from "@/lib/api/channels";
import { cn } from "@/lib/utils";

const TABS: { value: ConversationStatus; label: string }[] = [
  { value: "human", label: "Com atendente" },
  { value: "bot", label: "Com o agente" },
  { value: "closed", label: "Encerradas" },
];

const STATUS_LABEL: Record<string, string> = {
  human: "Com atendente",
  bot: "Com o agente",
  closed: "Encerrada",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function who(author: string, label: string | null | undefined): string {
  if (author === "customer") return "Cliente";
  if (author === "agent") return "Agente";
  if (author === "system") return "Aviso automático";
  return label ?? "Atendente";
}

function Conversation({ conversation }: { conversation: ConversationDetail }) {
  const act = useConversationAction(conversation.id);
  const [text, setText] = useState("");
  const human = conversation.status === "human";

  function run(args: Parameters<typeof act.mutate>[0], done?: string) {
    act.mutate(args, {
      onSuccess: () => {
        if (done) toast.success(done);
        if (args.action === "reply") setText("");
      },
      onError: (e) => toast.error(e.message),
    });
  }

  return (
    <section aria-label="Conversa" className="flex min-w-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-foreground text-[14px] font-medium">{conversation.user_id}</span>
        <Badge tone="neutral">
          {KIND_LABEL[conversation.channel_kind] ?? conversation.channel_kind} ·{" "}
          {conversation.channel_name}
        </Badge>
        <Badge tone={human ? "pending" : "neutral"}>{STATUS_LABEL[conversation.status]}</Badge>
      </div>
      {conversation.handoff_reason && (
        <p className="text-muted-foreground text-[12px]">
          Motivo da passagem: {conversation.handoff_reason}
          {conversation.assigned_label ? ` · com ${conversation.assigned_label}` : ""}
        </p>
      )}
      <ol className="border-border flex max-h-[60vh] flex-col gap-2 overflow-y-auto rounded border p-3">
        {conversation.messages.map((m) => (
          <li
            key={m.id}
            className={cn(
              "flex max-w-[85%] flex-col gap-0.5 rounded px-3 py-2 text-[13px]",
              m.direction === "in" ? "bg-muted self-start" : "bg-accent/10 self-end",
            )}
          >
            <span className="text-muted-foreground text-[11px]">
              {who(m.author, m.author_label)} · {when(m.created_at)}
            </span>
            <span className="text-foreground whitespace-pre-wrap">{m.text || "(sem texto)"}</span>
            {m.status === "failed" && (
              <span className="text-destructive text-[11px]">Não enviada: {m.error}</span>
            )}
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        {!human && (
          <Button
            size="sm"
            variant="accent"
            onClick={() => run({ action: "take" }, "Conversa assumida")}
          >
            Assumir
          </Button>
        )}
        {human && (
          <Button size="sm" onClick={() => run({ action: "release" }, "Devolvida ao agente")}>
            Devolver ao agente
          </Button>
        )}
        {conversation.status !== "closed" && (
          <Button size="sm" variant="muted" onClick={() => run({ action: "close" }, "Encerrada")}>
            Encerrar
          </Button>
        )}
      </div>
      {human && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) run({ action: "reply", text });
          }}
        >
          <label className="text-foreground text-[12px] font-medium" htmlFor="resposta">
            Responder pelo canal
          </label>
          <textarea
            id="resposta"
            rows={3}
            maxLength={4000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="border-border text-foreground focus:border-accent w-full rounded border bg-[var(--input)] px-3 py-2 text-[13px] focus:outline-none"
          />
          <Button
            size="sm"
            variant="accent"
            type="submit"
            className="self-end"
            disabled={act.isPending || !text.trim()}
          >
            {act.isPending ? "Enviando…" : "Enviar"}
          </Button>
        </form>
      )}
    </section>
  );
}

export default function ConversationsPage() {
  const [tab, setTab] = useState<ConversationStatus>("human");
  const [selected, setSelected] = useState<string | null>(null);
  const { data: list = [], isLoading, error } = useConversations(tab);
  const { data: detail } = useConversation(selected);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Conversas</h1>
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Conversas do WhatsApp e do Slack. As que passaram para uma pessoa esperam em &quot;Com
          atendente&quot;: o agente não responde até alguém devolver a conversa.
        </p>
        <div role="tablist" aria-label="Situação" className="flex flex-wrap gap-2">
          {TABS.map((t) => (
            <Button
              key={t.value}
              role="tab"
              aria-selected={tab === t.value}
              size="sm"
              variant={tab === t.value ? "accent" : "muted"}
              onClick={() => {
                setTab(t.value);
                setSelected(null);
              }}
            >
              {t.label}
            </Button>
          ))}
        </div>
        <div className="flex flex-col gap-4 md:flex-row">
          <ul aria-label="Fila" className="flex w-full flex-col md:w-80 md:flex-none">
            {isLoading && <li className="text-muted-foreground text-[13px]">Carregando…</li>}
            {error && <li className="text-destructive text-[13px]">{error.message}</li>}
            {!isLoading && !error && list.length === 0 && (
              <li className="text-muted-foreground text-[13px]">Nenhuma conversa aqui.</li>
            )}
            {list.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setSelected(c.id)}
                  className={cn(
                    "border-border flex w-full flex-col gap-0.5 border-t px-2 py-2 text-left text-[13px]",
                    selected === c.id ? "bg-muted" : "hover:bg-muted/50",
                  )}
                >
                  <span className="text-foreground font-medium">{c.user_id}</span>
                  <span className="text-muted-foreground truncate text-[12px]">
                    {c.last_message ?? "—"}
                  </span>
                  <span className="text-muted-foreground text-[11px]">
                    {c.channel_name} · {when(c.last_message_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {detail && selected ? (
            <Conversation conversation={detail} />
          ) : (
            <p className="text-muted-foreground text-[13px]">Escolha uma conversa na fila.</p>
          )}
        </div>
      </main>
    </div>
  );
}
