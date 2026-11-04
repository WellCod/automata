import type { components } from "@/lib/api/schema.d.ts";

export type AlertEvent = components["schemas"]["AlertDestinationResponse"]["events"][number];

// eventos que um destino de aviso da instância pode assinar (ADR-0021)
export const EVENT_LABELS: Record<AlertEvent, string> = {
  "budget.warning": "Orçamento perto do limite",
  "budget.exceeded": "Orçamento estourado",
  // orçamento de usuário ou token de integração (ADR-0031)
  "caller_budget.warning": "Orçamento de quem chama perto do limite",
  "caller_budget.exceeded": "Orçamento de quem chama estourado",
  "errors.spike": "Pico de erro",
  "suite.regressed": "Suíte regrediu",
  "suite.failing": "Suíte falhando",
  "suite.recovered": "Suíte voltou a passar",
  // pedidos do titular (ADR-0036)
  "data_subject.failed": "Pedido de titular falhou",
  "data_subject.due": "Pedido de titular perto do prazo",
  // operação (ADR-0037)
  "job.failed": "Run em background falhou",
  "cost.divergence": "Custo diferente do informado pelo provedor",
};

export const ALERT_EVENTS = Object.keys(EVENT_LABELS) as AlertEvent[];
