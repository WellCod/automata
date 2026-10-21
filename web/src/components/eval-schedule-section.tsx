"use client";

import { useState } from "react";
import { useEvalMutations, useEvalSchedule } from "@/lib/api/evals";
import { type EvalRunSummary, SCHEDULE_PRESETS } from "@/lib/eval-checks";
import { Button } from "@/components/ui/button";

const selectCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

const CUSTOM = "custom";

interface Props {
  configId: string;
  needsJudge: boolean;
  judgeModels: string[];
  // última execução, para mostrar quanto custa cada horário
  lastRun?: EvalRunSummary;
}

function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function EvalScheduleSection({ configId, needsJudge, judgeModels, lastRun }: Props) {
  const { data: schedule, isPending } = useEvalSchedule(configId);
  const { saveSchedule, deleteSchedule } = useEvalMutations(configId);
  // edição local por cima do que veio da API; null = ainda não mexeu
  const [preset, setPreset] = useState<string | null>(null);
  const [cron, setCron] = useState<string | null>(null);
  const [judge, setJudge] = useState<string | null>(null);

  const savedCron = schedule?.cron_expr ?? "";
  const savedPreset = SCHEDULE_PRESETS.some((p) => p.cron === savedCron)
    ? savedCron
    : savedCron
      ? CUSTOM
      : (SCHEDULE_PRESETS[1]?.cron ?? "");
  const chosen = preset ?? savedPreset;
  const expr = chosen === CUSTOM ? (cron ?? savedCron) : chosen;
  const judgeModel = judge ?? schedule?.judge_model ?? "";

  if (isPending) return null;

  return (
    <section aria-label="Agendamento" className="flex flex-col gap-2">
      <h3 className="text-foreground text-[13px] font-medium">Agendamento</h3>
      <p className="text-muted-foreground text-[12px]">
        Roda a suíte sozinha na versão vigente e pega o que muda por fora do prompt: modelo do
        provedor, base reindexada, servidor MCP.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Frequência"
          value={chosen}
          onChange={(e) => setPreset(e.target.value)}
          className={selectCls}
        >
          {SCHEDULE_PRESETS.map((p) => (
            <option key={p.cron} value={p.cron}>
              {p.label}
            </option>
          ))}
          <option value={CUSTOM}>Cron personalizado</option>
        </select>
        {chosen === CUSTOM && (
          <input
            aria-label="Expressão cron"
            value={expr}
            onChange={(e) => setCron(e.target.value)}
            placeholder="0 9 * * 1-5"
            className={`${selectCls} w-36 font-mono`}
          />
        )}
        {needsJudge && (
          <select
            aria-label="Modelo do juiz no agendamento"
            value={judgeModel}
            onChange={(e) => setJudge(e.target.value)}
            className={selectCls}
          >
            <option value="">Modelo do juiz</option>
            {judgeModels.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        )}
        <Button
          size="sm"
          variant="strong"
          disabled={!expr.trim() || saveSchedule.isPending}
          onClick={() =>
            saveSchedule.mutate({
              cron_expr: expr.trim(),
              timezone: schedule?.timezone ?? "America/Sao_Paulo",
              target: "current",
              judge_model: judgeModel || null,
              enabled: true,
            })
          }
        >
          {schedule ? "Salvar agendamento" : "Agendar"}
        </Button>
        {schedule && (
          <Button
            size="sm"
            variant="muted"
            disabled={deleteSchedule.isPending}
            onClick={() => deleteSchedule.mutate()}
          >
            Remover
          </Button>
        )}
      </div>
      {saveSchedule.isError && (
        <p className="text-destructive text-[12px]" role="alert">
          {saveSchedule.error.message}
        </p>
      )}
      {schedule && (
        <p className="text-muted-foreground text-[12px]" role="status">
          Próxima execução: {when(schedule.next_run_at)} ({schedule.timezone})
          {schedule.last_attempt_at && ` · último horário: ${when(schedule.last_attempt_at)}`}
        </p>
      )}
      {schedule?.last_error && (
        <p className="text-destructive text-[12px]">
          O último horário não rodou: {schedule.last_error}.
        </p>
      )}
      {lastRun?.cost != null && (
        <p className="text-muted-foreground text-[11px]">
          Cada execução custa por volta de{" "}
          {lastRun.cost.toLocaleString("pt-BR", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 4,
          })}{" "}
          ({lastRun.total_tokens.toLocaleString("pt-BR")} tokens na última).
        </p>
      )}
    </section>
  );
}
