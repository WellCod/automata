"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import type { RetrievalSettings } from "@/lib/api/knowledge";
import type { components } from "@/lib/api/schema.d.ts";

type CrossEncoderInfo = components["schemas"]["CrossEncoderInfo"];
type CrossEncoder = NonNullable<RetrievalSettings["cross_encoder"]>;

export const PROVIDER_LABELS: Record<CrossEncoder["provider"], string> = {
  cohere: "Cohere",
  bedrock: "AWS Bedrock",
};

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[13px] text-foreground focus:border-accent focus:outline-none";

export const DEFAULT_RETRIEVAL: RetrievalSettings = {
  reranker: "none",
  mmr_lambda: 0.5,
  recency_half_life_days: 30,
  recency_weight: 0.3,
  hyde: false,
  hyde_model: null,
  cross_encoder: null,
  agentic_filters: false,
};

export function useCrossEncoders() {
  return useQuery({
    queryKey: ["knowledge-bases", "cross-encoders"],
    queryFn: async (): Promise<CrossEncoderInfo[]> => {
      const res = await client.GET("/api/v1/knowledge-bases/cross-encoders");
      if (res.error) throw new Error("Falha ao carregar os cross-encoders");
      return res.data;
    },
  });
}

function usd(value: number): string {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 4,
  });
}

/** Cross-encoder antes da estratégia (ADR-0033); provedor sem configuração aparece desabilitado. */
export function CrossEncoderFields({
  value,
  onChange,
}: {
  value: RetrievalSettings;
  onChange: (v: RetrievalSettings) => void;
}) {
  const { data: providers = [] } = useCrossEncoders();
  const current = value.cross_encoder ?? null;
  const info = providers.find((p) => p.provider === current?.provider);
  return (
    <div className="flex flex-col gap-1">
      <label className="text-foreground flex items-center gap-2 text-[13px]">
        Ordenar por relevância com cross-encoder
        <select
          aria-label="Provedor do cross-encoder"
          value={current?.provider ?? ""}
          onChange={(e) => {
            const provider = e.target.value as CrossEncoder["provider"] | "";
            const found = providers.find((p) => p.provider === provider);
            onChange({
              ...value,
              cross_encoder: provider && found ? { provider, model: found.models[0] ?? "" } : null,
            });
          }}
          className={`${inputCls} w-auto`}
        >
          <option value="">Desligado</option>
          {providers.map((p) => (
            <option key={p.provider} value={p.provider} disabled={!p.configured}>
              {PROVIDER_LABELS[p.provider]}
              {p.configured ? "" : " (não configurado)"}
            </option>
          ))}
        </select>
      </label>
      {current && info && (
        <>
          <select
            aria-label="Modelo do cross-encoder"
            value={current.model ?? ""}
            onChange={(e) =>
              onChange({ ...value, cross_encoder: { ...current, model: e.target.value } })
            }
            className={`${inputCls} w-auto self-start`}
          >
            {info.models.map((m) => (
              <option key={m} value={m}>
                {m} · {usd(info.price_per_search[m] ?? 0)} por busca
              </option>
            ))}
          </select>
          <p className="text-muted-foreground text-[12px]">
            Lê a pergunta e cada candidato juntos e põe na frente o que responde, antes da
            reordenação acima. O texto dos candidatos vai para o provedor a cada busca, e o custo
            entra no consumo do agente.
          </p>
        </>
      )}
    </div>
  );
}

const RERANKERS: { value: RetrievalSettings["reranker"]; label: string; hint: string }[] = [
  { value: "none", label: "Busca simples", hint: "Os trechos mais próximos da pergunta." },
  {
    value: "mmr",
    label: "Diversidade (MMR)",
    hint: "Evita trechos repetidos no topo: útil em manuais longos e documentos duplicados.",
  },
  {
    value: "recency",
    label: "Recência",
    hint: "Prefere o trecho mais novo sem descartar o mais relevante: útil em políticas que mudam.",
  },
];

function useModels() {
  return useQuery({
    queryKey: ["models:capabilities"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/models/capabilities");
      if (res.error) throw new Error("Falha ao carregar modelos");
      return res.data as Record<string, unknown>;
    },
    select: (models) => Object.keys(models),
  });
}

export function RetrievalFields({
  value,
  onChange,
}: {
  value: RetrievalSettings;
  onChange: (v: RetrievalSettings) => void;
}) {
  const { data: models = [] } = useModels();
  const current = RERANKERS.find((r) => r.value === value.reranker);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-foreground mb-1 text-[13px] font-medium">Estratégia de busca</legend>
      <select
        aria-label="Reordenação dos trechos"
        value={value.reranker}
        onChange={(e) =>
          onChange({ ...value, reranker: e.target.value as RetrievalSettings["reranker"] })
        }
        className={`${inputCls} w-auto self-start`}
      >
        {RERANKERS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      {current && <p className="text-muted-foreground text-[12px]">{current.hint}</p>}
      {value.reranker === "mmr" && (
        <label className="text-muted-foreground flex items-center gap-2 text-[12px]">
          Diversidade
          <input
            type="range"
            aria-label="Peso da relevância no MMR"
            min={0}
            max={1}
            step={0.1}
            value={value.mmr_lambda}
            onChange={(e) => onChange({ ...value, mmr_lambda: Number(e.target.value) })}
          />
          Relevância ({value.mmr_lambda.toFixed(1)})
        </label>
      )}
      {value.reranker === "recency" && (
        <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-[12px]">
          <label className="flex items-center gap-1">
            Meia-vida
            <input
              type="number"
              aria-label="Meia-vida em dias"
              min={1}
              max={3650}
              value={value.recency_half_life_days}
              onChange={(e) =>
                onChange({ ...value, recency_half_life_days: Number(e.target.value) })
              }
              className={`${inputCls} w-20`}
            />
            dias
          </label>
          <label className="flex items-center gap-1">
            Peso da idade
            <input
              type="number"
              aria-label="Peso da recência"
              min={0}
              max={1}
              step={0.1}
              value={value.recency_weight}
              onChange={(e) => onChange({ ...value, recency_weight: Number(e.target.value) })}
              className={`${inputCls} w-16`}
            />
          </label>
        </div>
      )}
      <CrossEncoderFields value={value} onChange={onChange} />
      <label className="text-foreground mt-1 flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={value.agentic_filters ?? false}
          onChange={(e) => onChange({ ...value, agentic_filters: e.target.checked })}
        />
        Deixar o agente filtrar a busca pelos campos dos documentos
      </label>
      {value.agentic_filters && (
        <p className="text-muted-foreground text-[12px]">
          A busca do agente recebe os campos e valores dos documentos (até 20 por campo) e usa um
          deles quando a conversa já disser, como o produto do cliente. Filtro sem resultado cai na
          busca sem filtro.
        </p>
      )}
      <label className="text-foreground mt-1 flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={value.hyde}
          onChange={(e) => onChange({ ...value, hyde: e.target.checked })}
        />
        Buscar com uma resposta hipotética (HyDE)
      </label>
      {value.hyde && (
        <div className="flex flex-col gap-1">
          <select
            aria-label="Modelo do HyDE"
            value={value.hyde_model ?? ""}
            onChange={(e) => onChange({ ...value, hyde_model: e.target.value || null })}
            className={`${inputCls} w-auto self-start`}
          >
            <option value="">Modelo</option>
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <p className="text-muted-foreground text-[12px]">
            Uma chamada de modelo a mais por busca, que entra no consumo do agente. Ajuda quando a
            pergunta não usa as palavras do documento.
          </p>
        </div>
      )}
    </fieldset>
  );
}
