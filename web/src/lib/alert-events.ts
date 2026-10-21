import type { components } from "@/lib/api/schema.d.ts";

export type AlertEvent = components["schemas"]["AlertDestinationResponse"]["events"][number];

// eventos que um destino de aviso da instância pode assinar (ADR-0021)
export const EVENT_LABELS: Record<AlertEvent, string> = {
  "budget.warning": "Orçamento perto do limite",
  "budget.exceeded": "Orçamento estourado",
  "errors.spike": "Pico de erro",
  "suite.regressed": "Suíte regrediu",
  "suite.failing": "Suíte falhando",
  "suite.recovered": "Suíte voltou a passar",
};

export const ALERT_EVENTS = Object.keys(EVENT_LABELS) as AlertEvent[];
