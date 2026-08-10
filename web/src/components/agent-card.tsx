import { ArrowUpRight, Bot, MoreVertical } from "lucide-react";
import Link from "next/link";
import type { components } from "@/lib/api/schema.d.ts";

type AgentConfig = components["schemas"]["AgentConfigResponse"];

interface Props {
  agent: AgentConfig;
}

function IconMark() {
  return (
    <span className="bg-accent flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[2px]">
      <Bot className="text-accent-foreground h-3 w-3" aria-hidden />
    </span>
  );
}

function VersionSlot({ agent }: { agent: AgentConfig }) {
  if (agent.current_version) {
    return (
      <div className="flex items-baseline gap-1">
        <span className="text-label text-[11px] font-medium tracking-[0.05em] uppercase">
          Versão atual
        </span>
        <span className="text-accent text-[13px] font-medium">
          v{agent.current_version.version_number}
        </span>
        {agent.draft_version && (
          <span className="ml-1 text-[11px] tracking-[0.05em] text-amber-400 uppercase">
            · rascunho pendente
          </span>
        )}
      </div>
    );
  }
  if (agent.draft_version) {
    return (
      <div className="flex items-baseline gap-1">
        <span className="text-label text-[11px] font-medium tracking-[0.05em] uppercase">
          Rascunho
        </span>
        <span className="text-muted-foreground text-[13px]">sem versão publicada</span>
      </div>
    );
  }
  return (
    <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
      Sem versão
    </span>
  );
}

export function AgentCard({ agent }: Props) {
  return (
    <article className="border-border bg-card hover:border-foreground/20 flex flex-col rounded border p-3 transition-colors">
      {/* Header */}
      <div className="flex items-center gap-2">
        <IconMark />
        <span className="text-foreground min-w-0 flex-1 truncate text-sm font-medium">
          {agent.name}
        </span>
        <Link
          href={`/agents/${agent.id}`}
          className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 shrink-0 rounded transition-colors focus-visible:ring-2 focus-visible:outline-none"
          aria-label={`Abrir ${agent.name}`}
        >
          <ArrowUpRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>

      {/* Body */}
      <div className="mt-2 flex flex-1 flex-col gap-2">
        <div>
          <p className="text-label text-[11px] font-medium tracking-[0.05em] uppercase">
            Descrição
          </p>
          <p className="text-muted-foreground mt-0.5 line-clamp-2 text-[13px]">
            {agent.description ?? "—"}
          </p>
        </div>
        <VersionSlot agent={agent} />
      </div>

      {/* Footer */}
      <div className="border-border mt-3 flex items-center gap-2 border-t pt-2">
        <Link
          href={`/agents/${agent.id}?tab=test`}
          className="border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground focus-visible:ring-ring/50 inline-flex h-6 items-center rounded border px-2 text-[10px] font-medium tracking-[0.05em] uppercase transition-colors focus-visible:ring-2 focus-visible:outline-none"
        >
          Chat
        </Link>
        <Link
          href={`/agents/${agent.id}`}
          className="border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground focus-visible:ring-ring/50 inline-flex h-6 items-center rounded border px-2 text-[10px] font-medium tracking-[0.05em] uppercase transition-colors focus-visible:ring-2 focus-visible:outline-none"
        >
          Editar
        </Link>
        <button
          type="button"
          className="text-muted-foreground hover:border-border hover:text-foreground focus-visible:ring-ring/50 ml-auto flex h-6 w-6 items-center justify-center rounded border border-transparent transition-colors focus-visible:ring-2 focus-visible:outline-none"
          aria-label="Mais ações"
        >
          <MoreVertical className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </article>
  );
}
