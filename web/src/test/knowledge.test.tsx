import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import KnowledgeBasePage from "@/app/conhecimento/[id]/page";
import KnowledgeBasesPage from "@/app/conhecimento/page";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "kb1" }),
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

const base = {
  id: "kb1",
  name: "Políticas de RH",
  slug: "rh",
  description: "Férias e benefícios",
  embedder: "voyage",
  embedder_model: "voyage-3.5",
  dimensions: 1024,
  chunk_size: 2000,
  embedding_tokens: 1200,
  embedding_cost: 0.000072,
  updated_by: "editor",
  created_at: "2026-10-16T12:00:00Z",
  updated_at: "2026-10-16T12:00:00Z",
};

const content = (over: Record<string, unknown>) => ({
  id: "c1",
  base_id: "kb1",
  name: "ferias",
  source_type: "file",
  source: "ferias.pdf",
  extension: "pdf",
  size_bytes: 2048,
  status: "completed",
  status_message: null,
  chunk_count: 3,
  created_by: "editor",
  created_at: "2026-10-16T12:00:00Z",
  updated_at: "2026-10-16T12:00:00Z",
  ...over,
});

const embedders = [
  { name: "voyage", model: "voyage-3.5", dimensions: 1024, configured: true, default: true },
  {
    name: "openai",
    model: "text-embedding-3-small",
    dimensions: 1536,
    configured: false,
    default: false,
  },
];

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function mockGet(contents: unknown[] = [content({})]) {
  vi.mocked(client.GET).mockImplementation(async (path: string) => {
    if (path.endsWith("/embedders")) return { data: embedders, error: undefined } as never;
    if (path.endsWith("/contents")) return { data: contents, error: undefined } as never;
    if (path.endsWith("{base_id}")) return { data: base, error: undefined } as never;
    return { data: [base], error: undefined } as never;
  });
}

describe("KnowledgeBasesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet();
  });

  it("lista as bases com o nome da busca do agente", async () => {
    render(<KnowledgeBasesPage />, { wrapper });
    expect(await screen.findByText("Políticas de RH")).toBeInTheDocument();
    expect(screen.getByText(/buscar_rh/)).toBeInTheDocument();
  });

  it("cria base com identificador derivado do nome e embedder com chave", async () => {
    vi.mocked(client.POST).mockResolvedValue({
      data: { ...base, id: "kb2" },
      error: undefined,
    } as never);
    render(<KnowledgeBasesPage />, { wrapper });
    await userEvent.click(await screen.findByRole("button", { name: /nova base/i }));
    const form = screen.getByRole("form", { name: "Nova base" });
    await userEvent.type(within(form).getByLabelText("Nome"), "Manual de Operação");

    expect(within(form).getByLabelText("Identificador")).toHaveValue("manual_de_operacao");
    expect(within(form).getByRole("option", { name: /openai/ })).toBeDisabled();

    await userEvent.click(within(form).getByRole("button", { name: /criar base/i }));
    await waitFor(() => {
      expect(client.POST).toHaveBeenCalledWith("/api/v1/knowledge-bases", {
        body: expect.objectContaining({ slug: "manual_de_operacao", embedder: "voyage" }),
      });
    });
    expect(push).toHaveBeenCalledWith("/conhecimento/kb2");
  });
});

describe("KnowledgeBasePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("mostra documentos com estado e motivo da falha", async () => {
    mockGet([
      content({}),
      content({ id: "c2", name: "manual", status: "processing", chunk_count: 0 }),
      content({
        id: "c3",
        name: "site",
        status: "failed",
        status_message: "nenhum texto extraído",
      }),
    ]);
    render(<KnowledgeBasePage />, { wrapper });
    expect(await screen.findByText("3 trechos")).toBeInTheDocument();
    expect(screen.getByText("processando…")).toBeInTheDocument();
    expect(screen.getByText("nenhum texto extraído")).toBeInTheDocument();
  });

  it("envia arquivo como multipart", async () => {
    mockGet([]);
    vi.mocked(client.POST).mockResolvedValue({ data: content({}), error: undefined } as never);
    render(<KnowledgeBasePage />, { wrapper });
    const input = await screen.findByLabelText("Arquivos para a base");
    await userEvent.upload(input, new File(["conteúdo"], "politica.md", { type: "text/markdown" }));

    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    const [path, opts] = vi.mocked(client.POST).mock.calls[0] as unknown as [
      string,
      { body: FormData },
    ];
    expect(path).toBe("/api/v1/knowledge-bases/{base_id}/contents/file");
    expect(opts.body).toBeInstanceOf(FormData);
    expect((opts.body.get("file") as File).name).toBe("politica.md");
  });

  it("busca de teste mostra trecho, documento e relevância", async () => {
    mockGet();
    vi.mocked(client.POST).mockResolvedValue({
      data: [
        {
          content_id: "c1",
          content_name: "ferias",
          source: "ferias.pdf",
          text: "Trinta dias por ano.",
          score: 0.82,
        },
      ],
      error: undefined,
    } as never);
    render(<KnowledgeBasePage />, { wrapper });
    await userEvent.click(await screen.findByRole("tab", { name: /busca de teste/i }));
    await userEvent.type(screen.getByLabelText("Pergunta"), "quantos dias de férias");
    await userEvent.click(screen.getByRole("button", { name: /^buscar$/i }));

    expect(await screen.findByText("Trinta dias por ano.")).toBeInTheDocument();
    expect(screen.getByText("relevância 82%")).toBeInTheDocument();
  });

  it("mostra quem usa a base quando a remoção é recusada", async () => {
    mockGet();
    vi.mocked(client.DELETE).mockResolvedValue({
      data: undefined,
      error: { detail: "Base usada por: assistente-rh. Desligue antes de remover." },
    } as never);
    render(<KnowledgeBasePage />, { wrapper });
    await userEvent.click(await screen.findByRole("tab", { name: /configuração/i }));
    await userEvent.click(screen.getByRole("button", { name: /remover base/i }));
    await userEvent.click(screen.getByRole("button", { name: /confirmar remoção/i }));

    expect(await screen.findByText(/assistente-rh/)).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
