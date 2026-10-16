"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import { mergeSources, sourcesFromTool } from "@/lib/knowledge-sources";

type TraceSpan = components["schemas"]["TraceSpan"];

const TYPE_LABEL: Record<string, string> = {
  TEAM: "time",
  AGENT: "agente",
  LLM: "modelo",
  TOOL: "tool",
  WORKFLOW: "workflow",
};

function SpanNode({ span }: { span: TraceSpan }) {
  const failed = span.status === "ERROR";
  const children = span.spans ?? [];
  // busca em base de conhecimento: a saída é o JSON da tool; vale mostrar os documentos
  const sources =
    span.type === "TOOL"
      ? mergeSources([], sourcesFromTool({ tool_name: span.name, result: span.output }))
      : [];
  return (
    <li className="flex flex-col gap-1">
      <details className="group">
        <summary className="hover:bg-muted flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-[12px]">
          <span
            className={`w-14 flex-none text-[10px] tracking-[0.05em] uppercase ${failed ? "text-destructive" : "text-[var(--text-label)]"}`}
          >
            {TYPE_LABEL[span.type] ?? span.type.toLowerCase()}
          </span>
          <span className="text-foreground min-w-0 flex-1 truncate">{span.name}</span>
          <span className="text-muted-foreground flex-none">{span.duration}</span>
        </summary>
        <div className="border-border mt-1 ml-16 flex flex-col gap-1 border-l pl-2 text-[12px]">
          {span.error && <p className="text-destructive whitespace-pre-wrap">{span.error}</p>}
          {span.input && (
            <p className="text-muted-foreground line-clamp-6 whitespace-pre-wrap">
              <span className="text-foreground">entrada: </span>
              {span.input}
            </p>
          )}
          {sources.length > 0 && (
            <p className="text-muted-foreground">
              <span className="text-foreground">fontes: </span>
              {sources.map((src) => src.documento).join(", ")}
            </p>
          )}
          {span.output && (
            <p className="text-muted-foreground line-clamp-6 whitespace-pre-wrap">
              <span className="text-foreground">saída: </span>
              {span.output}
            </p>
          )}
        </div>
      </details>
      {children.length > 0 && (
        <ul className="border-border ml-2 flex flex-col gap-1 border-l pl-2">
          {children.map((child) => (
            <SpanNode key={child.id} span={child} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function RunTrace({ runId }: { runId: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["trace", runId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/runs/{run_id}/trace", {
        params: { path: { run_id: runId } },
      });
      if (res.error) {
        throw new Error(
          res.response.status === 404
            ? "Sem árvore para esta execução (tracing desligado ou run anterior a ele)."
            : "Não foi possível carregar a árvore.",
        );
      }
      return res.data!;
    },
    retry: false,
  });

  if (isPending) return <p className="text-muted-foreground text-[12px]">Carregando árvore…</p>;
  if (isError) return <p className="text-muted-foreground text-[12px]">{error.message}</p>;

  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-muted-foreground text-[11px]">
        {data.total_spans} etapas · {data.duration}
        {data.error_count > 0 && ` · ${data.error_count} com erro`}
      </p>
      <ul className="flex flex-col gap-1" aria-label="Árvore de execução">
        {data.tree.map((span) => (
          <SpanNode key={span.id} span={span} />
        ))}
      </ul>
    </div>
  );
}
