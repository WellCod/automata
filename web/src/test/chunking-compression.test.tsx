import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import KnowledgeBasePage from "@/app/conhecimento/[id]/page";
import { DEFAULT_CHUNKING, overlapProblem } from "@/components/chunking-settings";
import { DEFAULT_RUN, type RunControls, RunControlsEditor } from "@/components/run-controls-editor";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "kb1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

const base = {
  id: "kb1",
  name: "Manual",
  slug: "manual",
  description: "Políticas",
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
  updated_by: "editor",
  created_at: "2026-11-03T12:00:00Z",
  updated_at: "2026-11-03T12:00:00Z",
};

const MODELS = {
  "claude-sonnet-4-6": { extended_thinking: true, structured_output: true, vision: true },
  "claude-haiku-4-5": { extended_thinking: false, structured_output: true, vision: true },
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.GET).mockImplementation(async (path: string) => {
    if (path.endsWith("/contents")) return { data: [], error: undefined } as never;
    if (path.endsWith("/capabilities")) return { data: MODELS, error: undefined } as never;
    if (path.endsWith("/connectors")) return { data: [], error: undefined } as never;
    if (path.endsWith("/cross-encoders")) return { data: [], error: undefined } as never;
    return { data: base, error: undefined } as never;
  });
});

async function openSettings() {
  render(<KnowledgeBasePage />, { wrapper });
  await userEvent.click(await screen.findByRole("tab", { name: /configuração/i }));
}

describe("corte por base", () => {
  it("sobreposição acima de 30% do trecho é recusada antes de salvar", () => {
    expect(overlapProblem(1000, { ...DEFAULT_CHUNKING, overlap: 300 })).toBeNull();
    expect(overlapProblem(1000, { ...DEFAULT_CHUNKING, overlap: 301 })).toMatch(/30%/);
    expect(overlapProblem(1000, DEFAULT_CHUNKING)).toBeNull();
  });

  it("salva a estratégia por títulos com o nível escolhido", async () => {
    vi.mocked(client.PUT).mockResolvedValue({ data: base, error: undefined } as never);
    await openSettings();
    await userEvent.selectOptions(screen.getByLabelText("Estratégia de corte"), "headings");
    await userEvent.selectOptions(screen.getByLabelText("Nível de título"), "1");
    expect(screen.getByText(/Um trecho por seção de markdown/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    const [, opts] = vi.mocked(client.PUT).mock.calls[0] as unknown as [
      string,
      { body: { chunking: unknown } },
    ];
    expect(opts.body.chunking).toEqual({ strategy: "headings", overlap: null, heading_level: 1 });
  });

  it("sobreposição grande bloqueia o salvar e a prévia", async () => {
    await openSettings();
    await userEvent.type(screen.getByLabelText("Sobreposição entre trechos"), "900");
    expect(screen.getByRole("alert")).toHaveTextContent("30%");
    expect(screen.getByRole("button", { name: /^salvar$/i })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Texto para a prévia"), "# A\ntexto");
    expect(screen.getByRole("button", { name: "Ver trechos" })).toBeDisabled();
  });

  it("prévia mostra os trechos com o corte da tela, antes de salvar", async () => {
    vi.mocked(client.POST).mockResolvedValue({
      data: {
        chunks: ["# Férias\nTrinta dias.", "# Senha\nNoventa dias."],
        total: 2,
        chunk_size: 2000,
        chunking: { strategy: "headings", overlap: null, heading_level: 1 },
      },
      error: undefined,
    } as never);
    await openSettings();
    await userEvent.selectOptions(screen.getByLabelText("Estratégia de corte"), "headings");
    await userEvent.type(screen.getByLabelText("Texto para a prévia"), "# Férias");
    await userEvent.click(screen.getByRole("button", { name: "Ver trechos" }));
    const preview = await screen.findByRole("region", { name: "Prévia dos trechos" });
    await within(preview).findByText(/2 trechos/);
    expect(within(preview).getByText(/Trecho 2 · /)).toBeInTheDocument();
    const [path, opts] = vi.mocked(client.POST).mock.calls[0] as unknown as [
      string,
      { body: { chunking: { strategy: string }; text: string } },
    ];
    expect(path).toBe("/api/v1/knowledge-bases/{base_id}/chunk-preview");
    expect(opts.body.chunking.strategy).toBe("headings");
    expect(client.PUT).not.toHaveBeenCalled();
  });

  it("reprocessar pede confirmação, só com o corte salvo, e lista o que reenviar", async () => {
    vi.mocked(client.POST).mockResolvedValue({
      data: {
        queued: 3,
        skipped: 0,
        needs_upload: [
          {
            id: "old",
            base_id: "kb1",
            name: "contrato antigo",
            source_type: "file",
            source: "contrato.pdf",
            extension: "pdf",
            size_bytes: 10,
            status: "completed",
            status_message: null,
            chunk_count: 2,
            created_by: "x",
            created_at: "2026-10-01T12:00:00Z",
            updated_at: "2026-10-01T12:00:00Z",
          },
        ],
      },
      error: undefined,
    } as never);
    await openSettings();
    await userEvent.selectOptions(screen.getByLabelText("Estratégia de corte"), "fixed");
    expect(screen.getByRole("button", { name: "Reprocessar a base" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Estratégia de corte"), "recursive");
    await userEvent.click(screen.getByRole("button", { name: "Reprocessar a base" }));
    expect(client.POST).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar reprocessamento" }));
    const section = screen.getByRole("region", { name: "Reprocessar a base" });
    expect(await within(section).findByText("contrato antigo")).toBeInTheDocument();
    expect(vi.mocked(client.POST).mock.calls[0][0]).toBe(
      "/api/v1/knowledge-bases/{base_id}/reprocess",
    );
  });
});

describe("compressão do resultado de tool", () => {
  it("liga com os padrões e escolhe o modelo que resume", async () => {
    const seen: RunControls[] = [];
    function Harness() {
      const [value, setValue] = useState<RunControls>(DEFAULT_RUN);
      return (
        <RunControlsEditor
          value={value}
          onChange={(v) => {
            seen.push(v);
            setValue(v);
          }}
          modelId="claude-sonnet-4-6"
          capabilities={{ extended_thinking: false, structured_output: false, vision: false }}
        />
      );
    }
    render(<Harness />, { wrapper });
    expect(screen.queryByLabelText("Resultados antes de comprimir")).toBeNull();
    await userEvent.click(screen.getByLabelText("Comprimir o resultado das tools"));
    expect(seen.at(-1)?.compress_tool_results).toEqual({
      after_results: 3,
      token_limit: null,
      model_id: null,
    });
    const after = screen.getByLabelText("Resultados antes de comprimir");
    await userEvent.clear(after);
    await userEvent.type(after, "1");
    await userEvent.type(screen.getByLabelText("Tokens no contexto antes de comprimir"), "50000");
    await within(screen.getByLabelText("Modelo da compressão")).findByRole("option", {
      name: "claude-haiku-4-5",
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Modelo da compressão"),
      "claude-haiku-4-5",
    );
    expect(seen.at(-1)?.compress_tool_results).toEqual({
      after_results: 1,
      token_limit: 50000,
      model_id: "claude-haiku-4-5",
    });
    await userEvent.click(screen.getByLabelText("Comprimir o resultado das tools"));
    expect(seen.at(-1)?.compress_tool_results).toBeNull();
  });
});
