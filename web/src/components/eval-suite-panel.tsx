"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleSlash, Loader2, Pencil, Plus, Trash2, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { EvalCaseForm } from "@/components/eval-case-form";
import { EvalScheduleSection } from "@/components/eval-schedule-section";
import client from "@/lib/api/client";
import {
  useEvalCases,
  useEvalComparison,
  useEvalMutations,
  useEvalRun,
  useEvalRuns,
  useEvalSettings,
  useEvalSuggestion,
} from "@/lib/api/evals";
import {
  CHANGE_LABEL,
  CHECK_LABEL,
  type EvalCase,
  type EvalCaseInput,
  type EvalResult,
  type EvalRunSummary,
  hasJudge,
  RESULT_LABEL,
  runActive,
  TRIGGER_LABEL,
} from "@/lib/eval-checks";
import { blockLabel } from "@/lib/guardrail-labels";
import { Button } from "@/components/ui/button";
import { Badge, type BadgeTone } from "@/components/ui/status-badge";

interface VersionRef {
  id: string;
  version_number: number;
}

interface Props {
  configId: string;
  draftVersion?: VersionRef | null;
  currentVersion?: VersionRef | null;
  // run de conversa escolhido em "Virar caso de teste"; o painel abre o caso preenchido
  fromRun?: string | null;
  onFromRunDone?: () => void;
}

const selectCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

const RESULT_TONE: Record<EvalResult["status"], BadgeTone> = {
  passed: "active",
  failed: "danger",
  error: "danger",
  not_evaluated: "neutral",
};

function ResultIcon({ status }: { status: EvalResult["status"] }) {
  if (status === "passed")
    return <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-500" aria-hidden />;
  if (status === "not_evaluated")
    return <CircleSlash className="text-muted-foreground h-3.5 w-3.5" aria-hidden />;
  return <XCircle className="text-destructive h-3.5 w-3.5" aria-hidden />;
}

function runLabel(run: EvalRunSummary): string {
  const kind = run.version_status === "draft" ? "rascunho" : "publicada";
  const when = new Date(run.created_at).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  // manual é o padrão: só agendada e integração ganham marca
  const origin = run.trigger === "manual" ? "" : ` · ${TRIGGER_LABEL[run.trigger]}`;
  return `v${run.version_number} (${kind}) · ${when}${origin}`;
}

function usageLine(run: EvalRunSummary): string {
  const parts = [`${run.total_tokens.toLocaleString("pt-BR")} tokens`];
  if (run.cost != null)
    parts.push(
      run.cost.toLocaleString("pt-BR", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 4,
      }),
    );
  if (run.judge_model) parts.push(`juiz ${run.judge_model}`);
  return parts.join(" · ");
}

function checkSummary(check: EvalResult["checks"][number]): string {
  const type = String(check.type) as keyof typeof CHECK_LABEL;
  if (type === "text") {
    const rules = (check.rules as { kind: string; value: string; passed?: boolean }[]) ?? [];
    return rules.map((r) => `${r.passed === false ? "✗" : "✓"} ${r.kind} "${r.value}"`).join(" · ");
  }
  if (type === "tools") return `esperadas: ${((check.expected as string[]) ?? []).join(", ")}`;
  if (type === "steps") {
    const missing = (check.missing as string[] | undefined) ?? [];
    const extra = (check.extra as string[] | undefined) ?? [];
    const ran = (check.ran as string[] | undefined) ?? [];
    const parts = [`rodou: ${ran.length ? ran.join(" → ") : "nenhuma"}`];
    if (missing.length) parts.push(`faltou: ${missing.join(", ")}`);
    if (extra.length) parts.push(`fora da lista: ${extra.join(", ")}`);
    return parts.join(" · ");
  }
  if (type === "blocked") {
    const expected = check.rule ? blockLabel(String(check.rule)) : "qualquer regra";
    return check.blocked_by
      ? `esperado: ${expected} · barrou: ${blockLabel(String(check.blocked_by))}`
      : `esperado: ${expected} · respondeu sem bloquear`;
  }
  const score = check.score != null ? ` · nota ${String(check.score)}` : "";
  return `${String(check.reason ?? "")}${score}`;
}

function ResultItem({ result }: { result: EvalResult }) {
  const [open, setOpen] = useState(result.status !== "passed");
  return (
    <li
      aria-label={`${result.case_name}: ${RESULT_LABEL[result.status]}`}
      className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-2 text-left text-[13px]"
      >
        <ResultIcon status={result.status} />
        <span className="text-foreground font-medium">{result.case_name}</span>
        <Badge tone={RESULT_TONE[result.status]}>{RESULT_LABEL[result.status]}</Badge>
        {result.duration_ms != null && (
          <span className="text-muted-foreground ml-auto text-[11px]">
            {(result.duration_ms / 1000).toFixed(1)}s
          </span>
        )}
      </button>
      {open && (
        <div className="flex flex-col gap-1.5 pt-1 text-[12px]">
          <ul className="flex flex-col gap-1">
            {result.checks.map((check, i) => (
              <li key={i} className="flex gap-2">
                <span
                  className={
                    check.passed === true
                      ? "text-green-600 dark:text-green-500"
                      : check.passed === false
                        ? "text-destructive"
                        : "text-muted-foreground"
                  }
                >
                  {CHECK_LABEL[String(check.type) as keyof typeof CHECK_LABEL]}
                </span>
                <span className="text-muted-foreground">{checkSummary(check)}</span>
              </li>
            ))}
          </ul>
          {result.tools_called.length > 0 && (
            <p className="text-muted-foreground">
              Tools chamadas: {result.tools_called.join(", ")}
            </p>
          )}
          {result.error && <p className="text-destructive">{result.error}</p>}
          {result.output && (
            <p className="border-border text-foreground rounded border px-2 py-1 whitespace-pre-wrap">
              {result.output}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

function CaseItem({
  item,
  onEdit,
  onDelete,
  deleting,
}: {
  item: EvalCase;
  onEdit: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <li
      aria-label={`Caso ${item.name}`}
      className="border-border bg-card flex items-start gap-2 rounded border px-3 py-2"
    >
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-foreground text-[13px] font-medium">{item.name}</span>
        <span className="text-muted-foreground truncate text-[12px]">{item.input}</span>
        <span className="text-muted-foreground text-[11px]">
          {item.checks.map((c) => CHECK_LABEL[c.type]).join(" · ")}
        </span>
      </div>
      <Button size="icon" variant="ghost" aria-label={`Editar ${item.name}`} onClick={onEdit}>
        <Pencil aria-hidden />
      </Button>
      <Button
        size="icon"
        variant="ghost"
        aria-label={`Remover ${item.name}`}
        disabled={deleting}
        onClick={onDelete}
      >
        <Trash2 aria-hidden />
      </Button>
    </li>
  );
}

function useJudgeModels() {
  return useQuery({
    queryKey: ["models:capabilities"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/models/capabilities");
      if (res.error) throw new Error("Falha ao carregar modelos");
      return res.data as Record<string, { structured_output: boolean }>;
    },
    // o juiz responde num schema: só modelos com saída estruturada
    select: (models) =>
      Object.entries(models)
        .filter(([, caps]) => caps.structured_output)
        .map(([id]) => id),
  });
}

function SuggestedCase({
  configId,
  runId,
  saving,
  error,
  onSave,
  onDone,
}: {
  configId: string;
  runId: string;
  saving: boolean;
  error?: string | null;
  onSave: (body: EvalCaseInput) => void;
  onDone: () => void;
}) {
  const { data, isPending, error: loadError } = useEvalSuggestion(configId, runId);
  if (isPending)
    return (
      <p className="text-muted-foreground text-[13px]">Montando o caso a partir da conversa…</p>
    );
  if (loadError)
    return (
      <div className="flex items-center gap-2 text-[12px]" role="alert">
        <span className="text-destructive">{loadError.message}</span>
        <Button size="xs" variant="muted" onClick={onDone}>
          Fechar
        </Button>
      </div>
    );
  return (
    <EvalCaseForm
      key={runId}
      initial={{
        name: data.name,
        input: data.input,
        context: data.context,
        checks: data.checks,
        source_run_id: data.source_run_id,
      }}
      notes={data.notes}
      judgeSuggestion={data.judge_criteria}
      saving={saving}
      error={error}
      onCancel={onDone}
      onSave={onSave}
    />
  );
}

export function EvalSuitePanel({
  configId,
  draftVersion,
  currentVersion,
  fromRun,
  onFromRunDone,
}: Props) {
  const { data: cases = [], isPending: loadingCases } = useEvalCases(configId);
  const { data: runs = [] } = useEvalRuns(configId);
  const { data: settings } = useEvalSettings(configId);
  const { data: judgeModels = [] } = useJudgeModels();
  const { saveCase, deleteCase, startRun, updateSettings } = useEvalMutations(configId);

  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [chosenTarget, setTarget] = useState<string | null>(null);
  const [judge, setJudge] = useState<string>("");
  const [selected, setSelected] = useState<string | null>(null);

  // escolha vale enquanto for uma das versões oferecidas; rascunho novo volta ao padrão
  const offered = [draftVersion?.id, currentVersion?.id].filter(Boolean);
  const target =
    chosenTarget && offered.includes(chosenTarget)
      ? chosenTarget
      : (draftVersion?.id ?? currentVersion?.id ?? "");

  const viewing = selected ?? runs[0]?.id ?? null;
  const { data: detail } = useEvalRun(configId, viewing);

  // comparação padrão: última execução da vigente contra a última do rascunho
  const defaults = useMemo(() => {
    const onCurrent = runs.find((r) => r.version_id === currentVersion?.id && !runActive(r));
    const onDraft = runs.find((r) => r.version_id === draftVersion?.id && !runActive(r));
    return { base: onCurrent?.id ?? null, target: onDraft?.id ?? null };
  }, [runs, currentVersion?.id, draftVersion?.id]);
  const [base, setBase] = useState<string | null>(null);
  const [compareTarget, setCompareTarget] = useState<string | null>(null);
  const { data: comparison } = useEvalComparison(
    configId,
    base ?? defaults.base,
    compareTarget ?? defaults.target,
  );

  const needsJudge = hasJudge(cases);
  const busy = runs.some(runActive);
  const editingCase = cases.find((c) => c.id === editing);

  return (
    <div className="flex flex-col gap-6">
      <section aria-label="Gate de publicação" className="border-border rounded border px-3 py-2.5">
        <label className="text-foreground flex items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            checked={settings?.require_passing_evals ?? false}
            disabled={!settings || updateSettings.isPending}
            onChange={(e) => updateSettings.mutate(e.target.checked)}
          />
          Exigir suíte verde no rascunho para publicar
        </label>
        {settings?.require_passing_evals && (
          <p
            role="status"
            className={`mt-1 text-[12px] ${settings.can_publish ? "text-green-600 dark:text-green-500" : "text-muted-foreground"}`}
          >
            {settings.can_publish
              ? "Publicação liberada: a suíte passou no rascunho atual."
              : `Publicação bloqueada: ${settings.reason}.`}
          </p>
        )}
      </section>

      <section aria-label="Casos de teste" className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-foreground text-[13px] font-medium">
            Casos de teste <span className="text-muted-foreground">({cases.length})</span>
          </h3>
          {editing === null && (
            <Button size="sm" variant="accent" onClick={() => setEditing("new")}>
              <Plus aria-hidden />
              Novo caso
            </Button>
          )}
        </div>
        <p className="text-muted-foreground text-[12px]">
          Cada caso é uma mensagem e o que precisa ser verdade na resposta. Os casos não fazem parte
          da versão: editar o rascunho não muda o teste.
        </p>
        {fromRun && (
          <SuggestedCase
            configId={configId}
            runId={fromRun}
            saving={saveCase.isPending}
            error={saveCase.error?.message}
            onDone={() => onFromRunDone?.()}
            onSave={(body) => saveCase.mutate({ body }, { onSuccess: () => onFromRunDone?.() })}
          />
        )}
        {editing === "new" && (
          <EvalCaseForm
            saving={saveCase.isPending}
            error={saveCase.error?.message}
            onCancel={() => setEditing(null)}
            onSave={(body) => saveCase.mutate({ body }, { onSuccess: () => setEditing(null) })}
          />
        )}
        {loadingCases && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {!loadingCases && cases.length === 0 && editing === null && (
          <p className="text-muted-foreground border-border rounded border border-dashed px-3 py-4 text-center text-[13px]">
            Nenhum caso ainda. Comece pelo que não pode quebrar quando o prompt mudar.
          </p>
        )}
        <ul className="flex flex-col gap-1.5">
          {cases.map((item) =>
            editingCase?.id === item.id ? (
              <li key={item.id}>
                <EvalCaseForm
                  initial={{
                    name: item.name,
                    input: item.input,
                    context: item.context,
                    checks: item.checks,
                    source_run_id: item.source_run_id,
                  }}
                  saving={saveCase.isPending}
                  error={saveCase.error?.message}
                  onCancel={() => setEditing(null)}
                  onSave={(body) =>
                    saveCase.mutate({ id: item.id, body }, { onSuccess: () => setEditing(null) })
                  }
                />
              </li>
            ) : (
              <CaseItem
                key={item.id}
                item={item}
                deleting={deleteCase.isPending}
                onEdit={() => setEditing(item.id)}
                onDelete={() => deleteCase.mutate(item.id)}
              />
            ),
          )}
        </ul>
      </section>

      <section aria-label="Rodar a suíte" className="flex flex-col gap-2">
        <h3 className="text-foreground text-[13px] font-medium">Rodar</h3>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Versão testada"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className={selectCls}
          >
            {draftVersion && (
              <option value={draftVersion.id}>Rascunho (v{draftVersion.version_number})</option>
            )}
            {currentVersion && (
              <option value={currentVersion.id}>Vigente (v{currentVersion.version_number})</option>
            )}
          </select>
          {needsJudge && (
            <select
              aria-label="Modelo do juiz"
              value={judge}
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
            disabled={cases.length === 0 || !target || busy || startRun.isPending}
            onClick={() =>
              startRun.mutate(
                { version_id: target || null, judge_model: judge || null },
                { onSuccess: (run) => setSelected(run.id) },
              )
            }
          >
            {busy ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Rodando…
              </>
            ) : (
              "Rodar suíte"
            )}
          </Button>
        </div>
        {startRun.isError && (
          <p className="text-destructive text-[12px]" role="alert">
            {startRun.error.message}
          </p>
        )}
        <p className="text-muted-foreground text-[11px]">
          Cada caso roda o agente de verdade: os tokens contam no consumo, separados das conversas.
        </p>
      </section>

      <EvalScheduleSection
        configId={configId}
        needsJudge={needsJudge}
        judgeModels={judgeModels}
        lastRun={runs.find((r) => !runActive(r))}
      />

      {runs.length > 0 && (
        <section aria-label="Resultado" className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-foreground text-[13px] font-medium">Resultado</h3>
            <select
              aria-label="Execução exibida"
              value={viewing ?? ""}
              onChange={(e) => setSelected(e.target.value)}
              className={selectCls}
            >
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {runLabel(r)}
                </option>
              ))}
            </select>
          </div>
          {detail && (
            <>
              <p className="text-muted-foreground text-[12px]" role="status">
                {runActive(detail)
                  ? `Rodando… ${detail.results.length} de ${detail.total} casos`
                  : detail.status === "failed"
                    ? `A execução falhou: ${detail.error ?? "erro desconhecido"}`
                    : `${detail.passed} de ${detail.total} passaram` +
                      (detail.failed ? ` · ${detail.failed} falharam` : "") +
                      (detail.not_evaluated ? ` · ${detail.not_evaluated} não avaliados` : "") +
                      ` · ${usageLine(detail)}`}
              </p>
              <ul className="flex flex-col gap-1.5">
                {detail.results.map((r) => (
                  <ResultItem key={r.id} result={r} />
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {runs.filter((r) => !runActive(r)).length > 1 && (
        <section aria-label="Comparar execuções" className="flex flex-col gap-2">
          <h3 className="text-foreground text-[13px] font-medium">Comparar</h3>
          <div className="flex flex-wrap items-center gap-2 text-[12px]">
            <select
              aria-label="Execução base"
              value={base ?? defaults.base ?? ""}
              onChange={(e) => setBase(e.target.value || null)}
              className={selectCls}
            >
              <option value="">Base</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {runLabel(r)}
                </option>
              ))}
            </select>
            <span className="text-muted-foreground">contra</span>
            <select
              aria-label="Execução comparada"
              value={compareTarget ?? defaults.target ?? ""}
              onChange={(e) => setCompareTarget(e.target.value || null)}
              className={selectCls}
            >
              <option value="">Comparada</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {runLabel(r)}
                </option>
              ))}
            </select>
          </div>
          {comparison && (
            <>
              <p
                role="status"
                className={`text-[12px] ${comparison.regressions ? "text-destructive" : "text-muted-foreground"}`}
              >
                {comparison.regressions} regressão(ões) · {comparison.fixes} corrigido(s)
              </p>
              <ul aria-label="Casos comparados" className="flex flex-col gap-1 text-[12px]">
                {comparison.cases.map((c) => (
                  <li key={`${c.case_id}-${c.case_name}`} className="flex items-center gap-2">
                    <span className="text-foreground">{c.case_name}</span>
                    <span className="text-muted-foreground">
                      {c.base_status ? RESULT_LABEL[c.base_status] : "—"} →{" "}
                      {c.target_status ? RESULT_LABEL[c.target_status] : "—"}
                    </span>
                    <Badge
                      tone={
                        c.change === "regression"
                          ? "danger"
                          : c.change === "fix"
                            ? "active"
                            : "neutral"
                      }
                    >
                      {CHANGE_LABEL[c.change]}
                    </Badge>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </div>
  );
}
