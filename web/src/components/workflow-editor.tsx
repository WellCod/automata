"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Bot, GitBranch, Plus, Repeat, Split, Trash2 } from "lucide-react";
import client from "@/lib/api/client";
import {
  MAX_BRANCHES,
  MAX_DEPTH,
  type NodeType,
  RULE_KINDS,
  type StepNode,
  type StepReview,
  type WorkflowNode,
  type WorkflowRule,
  move,
  namesOf,
  newNode,
  removeAt,
  replaceAt,
  ruleNeedsValue,
  structureErrors,
} from "@/lib/workflow-tree";
import { Button } from "@/components/ui/button";

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

const TYPE_META: Record<NodeType, { label: string; icon: typeof Bot; hint: string }> = {
  step: { label: "Etapa", icon: Bot, hint: "Um agente ou time responde" },
  parallel: { label: "Paralelo", icon: Split, hint: "Ramos rodam ao mesmo tempo" },
  condition: { label: "Condição", icon: GitBranch, hint: "Escolhe o caminho por uma regra" },
  loop: { label: "Repetição", icon: Repeat, hint: "Repete até a regra ou o limite" },
};

type Executor = { key: string; name: string; kind: "agent" | "team" };

export function usePublishedExecutors() {
  return useQuery({
    queryKey: ["configs", "published-executors"],
    queryFn: async (): Promise<Executor[]> => {
      const load = async (kind: "agent" | "team") => {
        const res = await client.GET("/api/v1/configs", {
          params: { query: { kind, status: "published", page_size: 100 } },
        });
        if (res.error) throw new Error("Falha ao carregar agentes e times");
        return res.data!.items.map((c) => ({ key: `${kind}:${c.id}`, name: c.name, kind }));
      };
      const [agents, teams] = await Promise.all([load("agent"), load("team")]);
      return [...agents, ...teams];
    },
  });
}

interface Ctx {
  executors: Executor[];
  // nomes na árvore inteira: nó novo nunca repete nome
  taken: Set<string>;
  // fora de paralelo e de laço a etapa pode pausar para revisão humana (ADR-0023)
  reviewable: boolean;
}

function executorKey(step: StepNode): string {
  if (step.agent_id) return `agent:${step.agent_id}`;
  if (step.team_id) return `team:${step.team_id}`;
  return "";
}

function StepVersion({
  configId,
  value,
  onChange,
  label,
}: {
  configId: string;
  value: string | null;
  onChange: (versionId: string | null) => void;
  label: string;
}) {
  const { data: versions } = useQuery({
    queryKey: ["versions", configId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/versions", {
        params: { path: { config_id: configId } },
      });
      if (res.error) throw new Error("Falha ao carregar versões");
      return res.data!;
    },
  });
  const published = (versions ?? []).filter((v) => v.status === "published");
  // fixada numa versão que deixou de ser publicada: a API recusa ao salvar
  const stale = value != null && versions != null && !published.some((v) => v.id === value);
  return (
    <select
      aria-label={`Versão de ${label}`}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className={inputCls}
    >
      <option value="">Versão vigente</option>
      {stale && <option value={value}>Versão fixada indisponível</option>}
      {published.map((v) => (
        <option key={v.id} value={v.id}>
          Fixar v{v.version_number}
        </option>
      ))}
    </select>
  );
}

function StepFields({
  node,
  onChange,
  ctx,
}: {
  node: StepNode;
  onChange: (n: StepNode) => void;
  ctx: Ctx;
}) {
  const key = executorKey(node);
  const missing = key !== "" && !ctx.executors.some((e) => e.key === key);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        aria-label={`Quem executa ${node.name}`}
        value={key}
        onChange={(e) => {
          const [kind, id] = e.target.value.split(":");
          // trocar o executor solta a versão fixada, que era do anterior
          onChange({
            ...node,
            agent_id: kind === "agent" ? id : null,
            team_id: kind === "team" ? id : null,
            version_id: null,
          });
        }}
        className={`${inputCls} min-w-48`}
      >
        <option value="">Escolha um agente ou time</option>
        {missing && <option value={key}>Não publicado ou removido</option>}
        <optgroup label="Agentes">
          {ctx.executors
            .filter((e) => e.kind === "agent")
            .map((e) => (
              <option key={e.key} value={e.key}>
                {e.name}
              </option>
            ))}
        </optgroup>
        <optgroup label="Times">
          {ctx.executors
            .filter((e) => e.kind === "team")
            .map((e) => (
              <option key={e.key} value={e.key}>
                {e.name}
              </option>
            ))}
        </optgroup>
      </select>
      {key !== "" && (
        <StepVersion
          configId={key.slice(key.indexOf(":") + 1)}
          value={node.version_id ?? null}
          onChange={(version_id) => onChange({ ...node, version_id })}
          label={node.name}
        />
      )}
      <select
        aria-label={`Se ${node.name} falhar`}
        value={node.on_error}
        onChange={(e) => onChange({ ...node, on_error: e.target.value as StepNode["on_error"] })}
        className={inputCls}
      >
        <option value="stop">Se falhar, para o fluxo</option>
        <option value="continue">Se falhar, segue</option>
      </select>
      <label className="text-muted-foreground flex items-center gap-1 text-[12px]">
        Tentativas extras
        <input
          type="number"
          min={0}
          max={3}
          value={node.max_retries}
          onChange={(e) =>
            onChange({ ...node, max_retries: Math.min(3, Math.max(0, Number(e.target.value))) })
          }
          className={`${inputCls} w-14`}
        />
      </label>
      {(ctx.reviewable || node.review) && (
        <ReviewFields node={node} onChange={onChange} reviewable={ctx.reviewable} />
      )}
    </div>
  );
}

const NEW_REVIEW: StepReview = {
  when: "after",
  message: "",
  on_reject: "cancel",
  timeout_hours: null,
};

function ReviewFields({
  node,
  onChange,
  reviewable,
}: {
  node: StepNode;
  onChange: (n: StepNode) => void;
  reviewable: boolean;
}) {
  const review = node.review ?? null;
  const set = (next: Partial<StepReview>) =>
    onChange({ ...node, review: { ...(review ?? NEW_REVIEW), ...next } });
  return (
    <div className="flex w-full flex-col gap-1.5">
      <label className="text-foreground flex items-center gap-1.5 text-[12px]">
        <input
          type="checkbox"
          checked={review != null}
          onChange={(e) => onChange({ ...node, review: e.target.checked ? NEW_REVIEW : null })}
        />
        Pausar para revisão humana
      </label>
      {review && !reviewable && (
        <p className="text-destructive text-[11px]">
          Revisão humana não vale em paralelo nem em laço. Desmarque ou mova a etapa.
        </p>
      )}
      {review && (
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label={`Quando revisar ${node.name}`}
            value={review.when}
            onChange={(e) => {
              const when = e.target.value as StepReview["when"];
              // refazer só existe depois da saída: antes de rodar não há o que refazer
              set({
                when,
                on_reject:
                  when === "before" && review.on_reject === "retry" ? "cancel" : review.on_reject,
              });
            }}
            className={inputCls}
          >
            <option value="before">Confirmar antes de rodar</option>
            <option value="after">Aprovar a saída antes da próxima etapa</option>
          </select>
          <select
            aria-label={`Se recusarem ${node.name}`}
            value={review.on_reject}
            onChange={(e) => set({ on_reject: e.target.value as StepReview["on_reject"] })}
            className={inputCls}
          >
            <option value="cancel">Se recusarem, encerra o fluxo</option>
            <option value="skip">Se recusarem, pula a etapa</option>
            {review.when === "after" && (
              <option value="retry">Se recusarem, refaz com o motivo</option>
            )}
          </select>
          <label className="text-muted-foreground flex items-center gap-1 text-[12px]">
            Prazo
            <input
              type="number"
              min={1}
              max={168}
              placeholder="sem"
              value={review.timeout_hours ?? ""}
              onChange={(e) =>
                set({
                  timeout_hours: e.target.value
                    ? Math.min(168, Math.max(1, Number(e.target.value)))
                    : null,
                })
              }
              className={`${inputCls} w-16`}
            />
            horas
          </label>
          <input
            aria-label={`O que conferir em ${node.name}`}
            value={review.message ?? ""}
            maxLength={300}
            placeholder="O que o revisor precisa conferir"
            onChange={(e) => set({ message: e.target.value })}
            className={`${inputCls} min-w-56 flex-1`}
          />
        </div>
      )}
    </div>
  );
}

function RuleFields({
  rule,
  onChange,
  label,
  withSource,
}: {
  rule: WorkflowRule;
  onChange: (r: WorkflowRule) => void;
  label: string;
  withSource: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px]">
      {withSource ? (
        <select
          aria-label={`Origem da regra de ${label}`}
          value={rule.source}
          onChange={(e) => onChange({ ...rule, source: e.target.value as WorkflowRule["source"] })}
          className={inputCls}
        >
          <option value="input">A mensagem do usuário</option>
          <option value="previous">A resposta da etapa anterior</option>
        </select>
      ) : (
        <span className="text-muted-foreground">A resposta da volta</span>
      )}
      <select
        aria-label={`Regra de ${label}`}
        value={rule.kind}
        onChange={(e) => onChange({ ...rule, kind: e.target.value as WorkflowRule["kind"] })}
        className={inputCls}
      >
        {RULE_KINDS.map((k) => (
          <option key={k.value} value={k.value}>
            {k.label}
          </option>
        ))}
      </select>
      {ruleNeedsValue(rule.kind) && (
        <input
          aria-label={`Texto da regra de ${label}`}
          value={rule.value ?? ""}
          maxLength={200}
          placeholder="texto, sem diferenciar maiúsculas"
          onChange={(e) => onChange({ ...rule, value: e.target.value })}
          className={`${inputCls} min-w-40 flex-1`}
        />
      )}
    </div>
  );
}

function NodeCard({
  node,
  onChange,
  onMove,
  onRemove,
  canUp,
  canDown,
  canRemove,
  depth,
  ctx,
}: {
  node: WorkflowNode;
  onChange: (n: WorkflowNode) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
  canUp: boolean;
  canDown: boolean;
  canRemove: boolean;
  depth: number;
  ctx: Ctx;
}) {
  const meta = TYPE_META[node.type];
  const Icon = meta.icon;
  return (
    <li
      className="border-border bg-card flex flex-col gap-2 rounded border p-3"
      aria-label={`${meta.label} ${node.name}`}
    >
      <div className="flex items-center gap-2">
        <Icon className="text-accent h-3.5 w-3.5 flex-none" aria-hidden />
        <span className="text-muted-foreground w-16 flex-none text-[11px]">{meta.label}</span>
        <input
          aria-label={`Nome de ${meta.label.toLowerCase()} ${node.name}`}
          value={node.name}
          maxLength={60}
          onChange={(e) => onChange({ ...node, name: e.target.value })}
          className={`${inputCls} min-w-0 flex-1`}
        />
        <Button
          type="button"
          size="icon"
          variant="ghost"
          disabled={!canUp}
          onClick={() => onMove(-1)}
          aria-label={`Subir ${node.name}`}
        >
          <ArrowUp aria-hidden />
        </Button>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          disabled={!canDown}
          onClick={() => onMove(1)}
          aria-label={`Descer ${node.name}`}
        >
          <ArrowDown aria-hidden />
        </Button>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          disabled={!canRemove}
          onClick={onRemove}
          aria-label={`Remover ${node.name}`}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>

      {node.type === "step" && <StepFields node={node} onChange={onChange} ctx={ctx} />}

      {node.type === "parallel" && (
        <NodeList
          nodes={node.branches}
          onChange={(branches) => onChange({ ...node, branches: branches as StepNode[] })}
          depth={depth + 1}
          ctx={{ ...ctx, reviewable: false }}
          types={["step"]}
          min={2}
          max={MAX_BRANCHES}
          addLabel="Ramo"
        />
      )}

      {node.type === "condition" && (
        <>
          <div className="flex flex-col gap-1">
            <span className="text-foreground text-[12px] font-medium">Se</span>
            <RuleFields
              rule={node.rule}
              onChange={(rule) => onChange({ ...node, rule })}
              label={node.name}
              withSource
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-foreground text-[12px] font-medium">Então</span>
            <NodeList
              nodes={node.steps}
              onChange={(steps) => onChange({ ...node, steps })}
              depth={depth + 1}
              ctx={ctx}
              min={1}
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-foreground text-[12px] font-medium">Senão (opcional)</span>
            <NodeList
              nodes={node.else_steps ?? []}
              onChange={(else_steps) => onChange({ ...node, else_steps })}
              depth={depth + 1}
              ctx={ctx}
            />
          </div>
        </>
      )}

      {node.type === "loop" && (
        <>
          <div className="flex flex-wrap items-center gap-3 text-[12px]">
            <label className="text-muted-foreground flex items-center gap-1">
              Até
              <input
                type="number"
                min={1}
                max={10}
                value={node.max_iterations}
                onChange={(e) =>
                  onChange({
                    ...node,
                    max_iterations: Math.min(10, Math.max(1, Number(e.target.value))),
                  })
                }
                className={`${inputCls} w-14`}
              />
              voltas
            </label>
            <label className="text-foreground flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={node.until != null}
                onChange={(e) =>
                  onChange({
                    ...node,
                    until: e.target.checked
                      ? { kind: "contains", source: "previous", value: "" }
                      : null,
                  })
                }
              />
              Parar antes quando a resposta cumprir uma regra
            </label>
          </div>
          {node.until && (
            <RuleFields
              rule={node.until}
              onChange={(until) => onChange({ ...node, until })}
              label={node.name}
              withSource={false}
            />
          )}
          <NodeList
            nodes={node.steps}
            onChange={(steps) => onChange({ ...node, steps })}
            depth={depth + 1}
            ctx={{ ...ctx, reviewable: false }}
            min={1}
          />
        </>
      )}
    </li>
  );
}

function NodeList({
  nodes,
  onChange,
  depth,
  ctx,
  types,
  min = 0,
  max,
  addLabel,
}: {
  nodes: WorkflowNode[];
  onChange: (nodes: WorkflowNode[]) => void;
  depth: number;
  ctx: Ctx;
  types?: NodeType[];
  min?: number;
  max?: number;
  addLabel?: string;
}) {
  // contêiner só onde o filho ainda cabe dentro do limite de aninhamento
  const allowed = types ?? (depth < MAX_DEPTH ? (Object.keys(TYPE_META) as NodeType[]) : ["step"]);
  const full = max !== undefined && nodes.length >= max;
  return (
    <div className={depth > 1 ? "border-border ml-2 border-l pl-3" : undefined}>
      <ol className="flex flex-col gap-2">
        {nodes.map((node, i) => (
          <NodeCard
            key={i}
            node={node}
            depth={depth}
            ctx={ctx}
            canUp={i > 0}
            canDown={i < nodes.length - 1}
            canRemove={nodes.length > min}
            onChange={(n) => onChange(replaceAt(nodes, i, n))}
            onMove={(delta) => onChange(move(nodes, i, delta))}
            onRemove={() => onChange(removeAt(nodes, i))}
          />
        ))}
      </ol>
      {!full && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {allowed.map((type) => {
            const meta = TYPE_META[type];
            const label = addLabel ?? meta.label;
            return (
              <Button
                key={type}
                type="button"
                size="xs"
                variant="muted"
                title={meta.hint}
                onClick={() => onChange([...nodes, newNode(type, ctx.taken)])}
              >
                <Plus aria-hidden />
                {label}
              </Button>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface Props {
  value: WorkflowNode[];
  onChange: (value: WorkflowNode[]) => void;
}

export function WorkflowEditor({ value, onChange }: Props) {
  const { data: executors = [], isError } = usePublishedExecutors();
  const ctx: Ctx = { executors, taken: namesOf(value), reviewable: true };
  const errors = structureErrors(value);
  return (
    <fieldset className="border-border flex flex-col gap-3 rounded border px-4 pt-3 pb-4">
      <legend className="text-foreground px-1 text-[13px] font-medium">Etapas</legend>
      <p className="text-muted-foreground text-[11px]">
        Rodam de cima para baixo. Cada etapa recebe a resposta da anterior; os ramos de um paralelo
        recebem a mesma entrada. Só agentes e times publicados aparecem na lista.
      </p>
      {isError && (
        <p className="text-destructive text-[12px]" role="alert">
          Erro ao carregar agentes e times.
        </p>
      )}
      <NodeList nodes={value} onChange={onChange} depth={1} ctx={ctx} />
      {errors.length > 0 && value.length > 0 && (
        <ul className="text-muted-foreground list-disc pl-5 text-[11px]" aria-label="Pendências">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}
