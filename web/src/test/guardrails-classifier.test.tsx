import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import KnowledgeBasePage from "@/app/conhecimento/[id]/page";
import {
  DEFAULT_GUARDRAILS,
  type Guardrails,
  GuardrailsEditor,
  guardrailProblems,
} from "@/components/guardrails-editor";
import { blockLabel, screenedText } from "@/lib/guardrail-labels";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "kb1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

const MODELS = {
  "claude-haiku-4-5": { extended_thinking: false, structured_output: true, vision: true },
  "gpt-4o-mini": { extended_thinking: false, structured_output: true, vision: true },
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.GET).mockResolvedValue({ data: MODELS, error: undefined } as never);
});

function Harness({ seen }: { seen: Guardrails[] }) {
  const [value, setValue] = useState<Guardrails>(DEFAULT_GUARDRAILS);
  return (
    <GuardrailsEditor
      value={value}
      onChange={(v) => {
        seen.push(v);
        setValue(v);
      }}
    />
  );
}

describe("classificador por modelo", () => {
  it("liga com injeção, pede escopo para assunto e escolhe a falha", async () => {
    const seen: Guardrails[] = [];
    const user = userEvent.setup();
    render(<Harness seen={seen} />, { wrapper });
    await user.click(screen.getByLabelText(/Classificador por modelo/));
    expect(seen.at(-1)?.classifier).toEqual({
      model_id: "",
      checks: ["injection"],
      scope: "",
      on_failure: "allow",
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Escolha o modelo do classificador.");

    await screen.findByRole("option", { name: "gpt-4o-mini" });
    await user.selectOptions(screen.getByLabelText("Modelo que classifica"), "gpt-4o-mini");
    const checks = screen.getByRole("group", { name: "Checagens do classificador" });
    await user.click(within(checks).getByLabelText(/Assunto fora/));
    expect(screen.getByRole("alert")).toHaveTextContent("Descreva o que o agente atende");
    await user.type(screen.getByLabelText("O que o agente atende"), "pedidos da loja");
    await user.selectOptions(
      screen.getByLabelText("Se o classificador falhar ou passar de 10 s"),
      "block",
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(seen.at(-1)?.classifier).toEqual({
      model_id: "gpt-4o-mini",
      checks: ["injection", "off_topic"],
      scope: "pedidos da loja",
      on_failure: "block",
    });
  });

  it("exame de tool só usa o classificador quando ele está ligado", async () => {
    const seen: Guardrails[] = [];
    const user = userEvent.setup();
    render(<Harness seen={seen} />, { wrapper });
    await user.click(screen.getByLabelText(/Examinar o que as tools devolvem/));
    expect(seen.at(-1)?.tool_results).toEqual({ terms: true, classifier: false });
    const byClassifier = screen.getByLabelText(/Também pelo classificador/);
    expect(byClassifier).toBeDisabled();

    await user.click(screen.getByLabelText(/Classificador por modelo/));
    await user.click(screen.getByLabelText(/Também pelo classificador/));
    expect(seen.at(-1)?.tool_results).toEqual({ terms: true, classifier: true });
    // desligar o classificador volta o exame para só os termos
    await user.click(screen.getByLabelText(/Classificador por modelo/));
    expect(seen.at(-1)?.classifier).toBeNull();
    expect(seen.at(-1)?.tool_results).toEqual({ terms: true, classifier: false });
  });

  it("mesmas regras da API antes de salvar", () => {
    expect(guardrailProblems(DEFAULT_GUARDRAILS)).toEqual([]);
    expect(
      guardrailProblems({
        ...DEFAULT_GUARDRAILS,
        tool_results: { terms: false, classifier: false },
      }),
    ).toEqual(["O exame de tool precisa de termos ou classificador."]);
    expect(
      guardrailProblems({ ...DEFAULT_GUARDRAILS, tool_results: { terms: true, classifier: true } }),
    ).toEqual(["O exame de tool pelo classificador exige o classificador."]);
  });
});

describe("rótulos", () => {
  it("bloqueio do classificador e resultados retirados", () => {
    expect(blockLabel("classifier")).toBe("Classificador");
    expect(screenedText([{ tool: "rastrear" }])).toBe(
      "1 resultado de tool retirado por instrução embutida: rastrear",
    );
    expect(screenedText([{ tool: "a" }, { tool: "a" }, { tool: "b" }])).toBe(
      "3 resultados de tool retirados por instrução embutida: a, b",
    );
  });
});

describe("documentos com instrução embutida", () => {
  it("a lista da base marca o documento suspeito", async () => {
    const base = {
      id: "kb1",
      name: "Contratos",
      slug: "contratos",
      description: "",
      embedder: "voyage",
      embedder_model: "voyage-3.5",
      dimensions: 1024,
      chunk_size: 2000,
      retrieval: {
        reranker: "none",
        mmr_lambda: 0.5,
        recency_half_life_days: 30,
        recency_weight: 0.3,
        hyde: false,
        hyde_model: null,
      },
      chunking: { strategy: "recursive", overlap: null, heading_level: 2 },
      embedding_tokens: 0,
      embedding_cost: null,
      updated_by: "x",
      created_at: "2026-11-03T12:00:00Z",
      updated_at: "2026-11-03T12:00:00Z",
    };
    const content = (name: string, suspect_chunks: number) => ({
      id: name,
      base_id: "kb1",
      name,
      source_type: "file",
      source: `${name}.pdf`,
      extension: "pdf",
      size_bytes: 10,
      status: "completed",
      status_message: null,
      chunk_count: 4,
      suspect_chunks,
      created_by: "x",
      created_at: "2026-11-03T12:00:00Z",
      updated_at: "2026-11-03T12:00:00Z",
    });
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      if (path.endsWith("/contents"))
        return { data: [content("contrato", 2), content("manual", 0)], error: undefined } as never;
      if (path.endsWith("/connectors")) return { data: [], error: undefined } as never;
      return { data: base, error: undefined } as never;
    });
    render(<KnowledgeBasePage />, { wrapper });
    expect(await screen.findByText("2 com instrução embutida")).toBeInTheDocument();
    expect(screen.getAllByText(/com instrução embutida/)).toHaveLength(1);
  });
});
