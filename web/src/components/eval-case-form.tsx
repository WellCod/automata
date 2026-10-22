"use client";

import { Plus, Trash2 } from "lucide-react";
import { useId, useState } from "react";
import { blockLabel } from "@/lib/guardrail-labels";
import {
  availableTypes,
  BLOCK_RULES,
  type BlockRule,
  CHECK_LABEL,
  caseErrors,
  MAX_CONTEXT,
  type EvalCaseInput,
  type EvalCheck,
  newCheck,
  TEXT_KINDS,
  textNeedsValue,
} from "@/lib/eval-checks";
import { Button } from "@/components/ui/button";

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-2.5 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function CheckFields({
  check,
  onChange,
  index,
}: {
  check: EvalCheck;
  onChange: (c: EvalCheck) => void;
  index: number;
}) {
  if (check.type === "text") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground text-[12px]">A resposta</span>
        <select
          aria-label={`Regra da checagem ${index + 1}`}
          value={check.kind}
          onChange={(e) => onChange({ ...check, kind: e.target.value as typeof check.kind })}
          className={`${inputCls} w-auto`}
        >
          {TEXT_KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        {textNeedsValue(check.kind) && (
          <input
            aria-label={`Texto da checagem ${index + 1}`}
            value={check.value ?? ""}
            maxLength={200}
            placeholder="sem diferenciar maiúsculas"
            onChange={(e) => onChange({ ...check, value: e.target.value })}
            className={`${inputCls} min-w-40 flex-1`}
          />
        )}
      </div>
    );
  }
  if (check.type === "blocked") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground text-[12px]">O guardrail barra por</span>
        <select
          aria-label={`Regra do bloqueio da checagem ${index + 1}`}
          value={check.rule ?? ""}
          onChange={(e) => onChange({ ...check, rule: (e.target.value || null) as BlockRule })}
          className={`${inputCls} w-auto`}
        >
          <option value="">qualquer regra</option>
          {BLOCK_RULES.map((rule) => (
            <option key={rule} value={rule}>
              {blockLabel(rule)}
            </option>
          ))}
        </select>
      </div>
    );
  }
  if (check.type === "tools") {
    return (
      <div className="flex flex-col gap-1.5">
        <input
          aria-label={`Tools da checagem ${index + 1}`}
          defaultValue={check.tools.join(", ")}
          placeholder="buscar_politicas_atendimento, crm_consultar_cliente"
          // separa na saída do campo: vírgula no meio da digitação não vira tool vazia
          onBlur={(e) =>
            onChange({
              ...check,
              tools: [
                ...new Set(
                  e.target.value
                    .split(",")
                    .map((t) => t.trim())
                    .filter(Boolean),
                ),
              ],
            })
          }
          className={inputCls}
        />
        <label className="text-muted-foreground flex items-center gap-1.5 text-[12px]">
          <input
            type="checkbox"
            checked={!check.allow_additional}
            onChange={(e) => onChange({ ...check, allow_additional: !e.target.checked })}
          />
          Reprovar se chamar outras tools além destas
        </label>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1.5">
      <textarea
        aria-label={`Critério da checagem ${index + 1}`}
        value={check.criteria}
        rows={2}
        maxLength={1000}
        placeholder="Ex.: responde com o prazo de troca e cita a política, sem prometer exceção"
        onChange={(e) => onChange({ ...check, criteria: e.target.value })}
        className={`${inputCls} resize-y`}
      />
      <div className="flex flex-wrap items-center gap-2 text-[12px]">
        <select
          aria-label={`Modo do juiz da checagem ${index + 1}`}
          value={check.mode}
          onChange={(e) => onChange({ ...check, mode: e.target.value as typeof check.mode })}
          className={`${inputCls} w-auto`}
        >
          <option value="binary">Aprova ou reprova</option>
          <option value="numeric">Nota de 1 a 10</option>
        </select>
        {check.mode === "numeric" && (
          <label className="text-muted-foreground flex items-center gap-1">
            aprova com nota
            <input
              type="number"
              min={1}
              max={10}
              value={check.threshold}
              onChange={(e) =>
                onChange({
                  ...check,
                  threshold: Math.min(10, Math.max(1, Number(e.target.value))),
                })
              }
              className={`${inputCls} w-14`}
            />
            ou mais
          </label>
        )}
      </div>
    </div>
  );
}

interface Props {
  initial?: EvalCaseInput;
  // vindo de uma conversa real: avisos (dados mascarados, contexto cortado) e critério sugerido
  notes?: string[];
  judgeSuggestion?: string | null;
  saving: boolean;
  error?: string | null;
  onSave: (value: EvalCaseInput) => void;
  onCancel: () => void;
}

export function EvalCaseForm({
  initial,
  notes,
  judgeSuggestion,
  saving,
  error,
  onSave,
  onCancel,
}: Props) {
  const id = useId();
  const [value, setValue] = useState<EvalCaseInput>(
    initial ?? { name: "", input: "", checks: [newCheck("text")] },
  );
  const errors = caseErrors(value);
  const setCheck = (i: number, c: EvalCheck) =>
    setValue((v) => ({ ...v, checks: v.checks.map((old, j) => (j === i ? c : old)) }));
  const context = value.context ?? [];
  const setContext = (next: string[]) => setValue((v) => ({ ...v, context: next }));
  const canSuggestJudge = !!judgeSuggestion && availableTypes(value.checks).includes("judge");

  return (
    <form
      aria-label={
        initial?.source_run_id
          ? "Caso da conversa"
          : initial
            ? `Editar ${initial.name}`
            : "Novo caso"
      }
      onSubmit={(e) => {
        e.preventDefault();
        if (errors.length === 0) onSave({ ...value, name: value.name.trim() });
      }}
      className="border-border bg-card flex flex-col gap-3 rounded border p-3"
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-name`} className="text-foreground text-[12px] font-medium">
          Nome do caso
        </label>
        <input
          id={`${id}-name`}
          value={value.name}
          maxLength={80}
          placeholder="prazo de troca"
          onChange={(e) => setValue({ ...value, name: e.target.value })}
          className={inputCls}
        />
      </div>
      {notes && notes.length > 0 && (
        <ul className="text-muted-foreground flex flex-col gap-0.5 text-[12px]" role="note">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-foreground mb-1 text-[12px] font-medium">
          Conversa antes da mensagem (opcional)
        </legend>
        <p className="text-muted-foreground text-[11px]">
          Rodam na mesma sessão antes da mensagem de entrada; só a resposta a ela é checada.
        </p>
        {context.map((message, i) => (
          <div key={i} className="flex items-start gap-1.5">
            <textarea
              aria-label={`Mensagem anterior ${i + 1}`}
              value={message}
              rows={1}
              maxLength={4000}
              onChange={(e) => setContext(context.map((m, j) => (j === i ? e.target.value : m)))}
              className={`${inputCls} resize-y`}
            />
            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label={`Remover mensagem anterior ${i + 1}`}
              onClick={() => setContext(context.filter((_, j) => j !== i))}
            >
              <Trash2 aria-hidden />
            </Button>
          </div>
        ))}
        {context.length < MAX_CONTEXT && (
          <div>
            <Button
              type="button"
              size="xs"
              variant="muted"
              onClick={() => setContext([...context, ""])}
            >
              <Plus aria-hidden />
              Mensagem anterior
            </Button>
          </div>
        )}
      </fieldset>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-input`} className="text-foreground text-[12px] font-medium">
          Mensagem de entrada
        </label>
        <textarea
          id={`${id}-input`}
          value={value.input}
          rows={2}
          maxLength={4000}
          placeholder="Comprei há 10 dias e quero trocar, ainda dá?"
          onChange={(e) => setValue({ ...value, input: e.target.value })}
          className={`${inputCls} resize-y`}
        />
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-foreground mb-1 text-[12px] font-medium">
          O que precisa ser verdade na resposta
        </legend>
        <ol className="flex flex-col gap-2">
          {value.checks.map((check, i) => (
            <li
              key={i}
              aria-label={`Checagem ${i + 1}: ${CHECK_LABEL[check.type]}`}
              className="border-border flex flex-col gap-1.5 rounded border p-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground text-[11px] font-medium">
                  {CHECK_LABEL[check.type]}
                </span>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Remover checagem ${i + 1}`}
                  onClick={() =>
                    setValue({ ...value, checks: value.checks.filter((_, j) => j !== i) })
                  }
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
              <CheckFields check={check} index={i} onChange={(c) => setCheck(i, c)} />
            </li>
          ))}
        </ol>
        <div className="flex flex-wrap gap-1.5">
          {canSuggestJudge && (
            <Button
              type="button"
              size="xs"
              variant="accent"
              onClick={() =>
                setValue({
                  ...value,
                  checks: [
                    ...value.checks,
                    { type: "judge", criteria: judgeSuggestion!, mode: "binary", threshold: 7 },
                  ],
                })
              }
            >
              <Plus aria-hidden />
              Critério sugerido pela resposta original
            </Button>
          )}
          {availableTypes(value.checks).map((type) => (
            <Button
              key={type}
              type="button"
              size="xs"
              variant="muted"
              onClick={() => setValue({ ...value, checks: [...value.checks, newCheck(type)] })}
            >
              <Plus aria-hidden />
              {CHECK_LABEL[type]}
            </Button>
          ))}
        </div>
      </fieldset>

      {(error || (errors.length > 0 && value.name)) && (
        <p className="text-destructive text-[12px]" role="alert">
          {error ?? errors[0]}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="muted" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" variant="strong" disabled={saving || errors.length > 0}>
          {saving ? "Salvando…" : "Salvar caso"}
        </Button>
      </div>
    </form>
  );
}
