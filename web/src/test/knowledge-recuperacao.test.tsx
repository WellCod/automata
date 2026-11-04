import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import KnowledgeBasePage from "@/app/conhecimento/[id]/page";
import { formatFields, parseFields } from "@/components/document-fields";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "kb1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

const retrieval = {
  reranker: "none",
  mmr_lambda: 0.5,
  recency_half_life_days: 30,
  recency_weight: 0.3,
  hyde: false,
  hyde_model: null,
  cross_encoder: null,
  agentic_filters: false,
};

const base = {
  id: "kb1",
  name: "Manuais",
  slug: "manuais",
  description: "Planos",
  embedder: "voyage",
  embedder_model: "voyage-3.5",
  dimensions: 1024,
  chunk_size: 2000,
  retrieval,
  embedding_tokens: 0,
  embedding_cost: null,
  updated_by: "editor",
  created_at: "2026-11-04T12:00:00Z",
  updated_at: "2026-11-04T12:00:00Z",
};

const content = {
  id: "c1",
  base_id: "kb1",
  name: "manual plano a",
  source_type: "text",
  source: "manual plano a",
  extension: "txt",
  size_bytes: 120,
  status: "completed",
  status_message: null,
  chunk_count: 1,
  created_by: "editor",
  created_at: "2026-11-04T12:00:00Z",
  updated_at: "2026-11-04T12:00:00Z",
  fields: { plano: "a" },
};

const crossEncoders = [
  {
    provider: "cohere",
    models: ["rerank-v3.5", "rerank-multilingual-v3.0"],
    configured: true,
    price_per_search: { "rerank-v3.5": 0.002, "rerank-multilingual-v3.0": 0.002 },
  },
  {
    provider: "bedrock",
    models: ["cohere.rerank-v3-5:0", "amazon.rerank-v1:0"],
    configured: false,
    price_per_search: { "cohere.rerank-v3-5:0": 0.002, "amazon.rerank-v1:0": 0.001 },
  },
];

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function mockGet(current = base) {
  vi.mocked(client.GET).mockImplementation((async (path: string) => {
    if (path.endsWith("/cross-encoders")) return { data: crossEncoders, error: undefined };
    if (path.endsWith("/embedders")) return { data: [], error: undefined };
    if (path.endsWith("/contents")) return { data: [content], error: undefined };
    if (path.endsWith("/capabilities")) return { data: {}, error: undefined };
    return { data: current, error: undefined };
  }) as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockGet();
});

describe("campos do documento", () => {
  it("lê campo=valor por linha ou vírgula e aponta o que a API recusa", () => {
    expect(parseFields("plano=a, ano=2026").fields).toEqual({ plano: "a", ano: "2026" });
    expect(parseFields("Plano=a\nsem igual").problems).toHaveLength(2);
    expect(formatFields({ plano: "a", ano: "2026" })).toBe("plano=a\nano=2026");
  });

  it("mostra os campos e salva a edição no documento", async () => {
    vi.mocked(client.PUT).mockResolvedValue({ data: content, error: undefined } as never);
    const user = userEvent.setup();
    render(<KnowledgeBasePage />, { wrapper });
    const chips = await screen.findByRole("list", { name: "Campos do documento" });
    expect(within(chips).getByText("a")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Campos" }));
    const group = screen.getByRole("group", { name: "Campos de manual plano a" });
    const box = within(group).getByRole("textbox");
    await user.clear(box);
    await user.type(box, "plano=premium{enter}ano=2026");
    await user.click(within(group).getByRole("button", { name: "Salvar campos" }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    const [path, opts] = vi.mocked(client.PUT).mock.calls[0] as unknown as [
      string,
      { body: unknown },
    ];
    expect(path).toBe("/api/v1/knowledge-bases/{base_id}/contents/{content_id}/fields");
    expect(opts.body).toEqual({ fields: { plano: "premium", ano: "2026" } });
  });
});

describe("cross-encoder e filtros", () => {
  it("só oferece provedor configurado e salva com o modelo padrão e os filtros", async () => {
    vi.mocked(client.PUT).mockResolvedValue({ data: base, error: undefined } as never);
    const user = userEvent.setup();
    render(<KnowledgeBasePage />, { wrapper });
    await user.click(await screen.findByRole("tab", { name: /configuração/i }));
    const provider = await screen.findByLabelText("Provedor do cross-encoder");
    await waitFor(() =>
      expect(within(provider).getByRole("option", { name: /AWS Bedrock/ })).toBeDisabled(),
    );
    await user.selectOptions(provider, "cohere");
    expect(screen.getByText(/O texto dos candidatos vai para o provedor/)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/filtrar a busca pelos campos/));
    await user.click(screen.getByRole("button", { name: /^salvar$/i }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    const [, opts] = vi.mocked(client.PUT).mock.calls[0] as unknown as [
      string,
      { body: { retrieval: unknown } },
    ];
    expect(opts.body.retrieval).toMatchObject({
      cross_encoder: { provider: "cohere", model: "rerank-v3.5" },
      agentic_filters: true,
    });
  });

  it("busca de teste manda os filtros e avisa quando caem", async () => {
    mockGet({
      ...base,
      retrieval: { ...retrieval, cross_encoder: { provider: "cohere", model: "rerank-v3.5" } },
    } as never);
    const hit = {
      content_id: "c1",
      content_name: "manual plano a",
      source: null,
      text: "t",
      score: 0.4,
    };
    vi.mocked(client.POST).mockResolvedValue({
      data: {
        with_strategy: {
          hits: [hit],
          searched: "cancelar",
          hyde_tokens: 0,
          rerank_cost: 0.002,
          filters_dropped: true,
        },
        without_strategy: {
          hits: [hit],
          searched: "cancelar",
          hyde_tokens: 0,
          filters_dropped: true,
        },
        retrieval,
      },
      error: undefined,
    } as never);
    const user = userEvent.setup();
    render(<KnowledgeBasePage />, { wrapper });
    await user.click(await screen.findByRole("tab", { name: /busca de teste/i }));
    await user.type(screen.getByLabelText("Pergunta"), "cancelar");
    await user.type(screen.getByPlaceholderText("produto=plano a, ano=2026"), "plano=c");
    await user.click(screen.getByRole("button", { name: /^buscar$/i }));
    const col = await screen.findByRole("region", { name: "Com a estratégia da base" });
    expect(within(col).getByText(/Cross-encoder/)).toBeInTheDocument();
    expect(within(col).getByText(/a busca saiu sem ele/)).toBeInTheDocument();
    const [, opts] = vi.mocked(client.POST).mock.calls.at(-1) as unknown as [
      string,
      { body: unknown },
    ];
    expect(opts.body).toEqual({ query: "cancelar", max_results: 5, filters: { plano: "c" } });
  });
});
