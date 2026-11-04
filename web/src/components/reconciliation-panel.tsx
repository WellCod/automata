"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import { formatTotalUsd } from "@/lib/format";

const PROVIDER_LABELS: Record<string, string> = { anthropic: "Anthropic", openai: "OpenAI" };

/** Custo informado pelo provedor e estimado pelo Automata, por dia (ADR-0037). */
export function ReconciliationPanel() {
  const { data } = useQuery({
    queryKey: ["metrics", "reconciliation"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/metrics/reconciliation", {
        params: { query: { days: 14 } },
      });
      if (res.error) throw new Error("Falha ao carregar a conciliação");
      return res.data;
    },
  });
  // sem chave admin de nenhum provedor, a seção não aparece
  const providers = data?.providers ?? [];
  const reported = data?.rows ?? [];
  if (!data || (providers.length === 0 && reported.length === 0)) return null;
  const rows = [...reported].reverse();
  return (
    <section aria-labelledby="conciliacao" className="mb-8 flex flex-col gap-2">
      <h2 id="conciliacao" className="text-foreground text-[13px] font-medium">
        Conciliação com o provedor
      </h2>
      <p className="text-muted-foreground text-[12px]">
        O custo que o provedor informou e o que o Automata estimou pela tabela de preços. Só bate se
        a chave do provedor for usada só por esta instância. Dia aberto ainda recebe custo.
      </p>
      {rows.length === 0 ? (
        <p className="text-muted-foreground text-[13px]">
          Nenhum relatório lido ainda. A leitura acontece de hora em hora.
        </p>
      ) : (
        <div className="max-w-full min-w-0 overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="text-muted-foreground text-[12px]">
              <tr>
                <th className="py-1.5 pr-3 font-normal">Dia</th>
                <th className="py-1.5 pr-3 font-normal">Provedor</th>
                <th className="py-1.5 pr-3 font-normal">Informado</th>
                <th className="py-1.5 pr-3 font-normal">Estimado</th>
                <th className="py-1.5 font-normal">Diferença</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const off =
                  r.closed &&
                  r.diff_percent != null &&
                  Math.abs(r.diff_percent) >= data.alert_percent;
                return (
                  <tr key={`${r.provider}-${r.day}`} className="border-border border-t">
                    <td className="py-1.5 pr-3">
                      {new Date(`${r.day}T12:00:00Z`).toLocaleDateString("pt-BR")}
                      {!r.closed && (
                        <span className="text-muted-foreground block text-[11px]">em aberto</span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3">{PROVIDER_LABELS[r.provider] ?? r.provider}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{formatTotalUsd(r.reported_usd)}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{formatTotalUsd(r.estimated_usd)}</td>
                    <td
                      className={`py-1.5 tabular-nums ${off ? "text-destructive font-medium" : ""}`}
                    >
                      {r.diff_percent == null
                        ? "—"
                        : `${r.diff_percent > 0 ? "+" : ""}${r.diff_percent.toLocaleString("pt-BR")}%`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
