import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KnowledgeConnectors } from "@/components/knowledge-connectors";
import { origin, summaryText } from "@/lib/api/connectors";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const connector = {
  id: "c1",
  base_id: "b1",
  kind: "github",
  name: "Documentação",
  settings: { repo: "acme/docs", branch: "main", path: "docs", api_url: "https://api.github.com" },
  has_secret: true,
  last_status: "ok",
  last_message: null,
  last_summary: { added: 2, updated: 1, removed: 0, unchanged: 3, failed: 0, skipped: 1 },
  last_sync_at: "2026-10-21T10:00:00Z",
  sync_every_hours: 24,
  next_sync_at: "2026-10-22T10:00:00Z",
  content_count: 6,
  created_by: "owner",
  created_at: "2026-10-21T09:00:00Z",
} as const;

function mockGet(role: "owner" | "editor") {
  vi.mocked(client.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/me")
      return { data: { id: "u", email: "x@y.z", role }, error: undefined } as never;
    return { data: [connector], error: undefined } as never;
  });
}

describe("conectores da base", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.POST).mockResolvedValue({ data: connector, error: undefined } as never);
    vi.mocked(client.PUT).mockResolvedValue({ data: connector, error: undefined } as never);
  });

  it("resume a origem e a última sincronização", () => {
    expect(origin(connector)).toBe("acme/docs@main/docs");
    expect(origin({ kind: "s3", settings: { bucket: "b", prefix: "p" } })).toBe("b/p");
    expect(summaryText(connector.last_summary)).toBe(
      "2 novo(s) · 1 atualizado(s) · 0 removido(s) · 3 sem mudança · 1 fora (tipo ou tamanho)",
    );
  });

  it("owner cadastra conector do GitHub sem mandar campo vazio", async () => {
    mockGet("owner");
    const user = userEvent.setup();
    render(<KnowledgeConnectors baseId="b1" />, { wrapper });
    await user.click(await screen.findByRole("button", { name: "Novo conector" }));
    const form = screen.getByRole("form", { name: "Novo conector" });
    await user.type(within(form).getByLabelText("Nome do conector"), "Docs");
    await user.type(within(form).getByLabelText("Repositório"), "acme/docs");
    await user.type(within(form).getByLabelText("Pasta"), "docs");
    await user.type(
      within(form).getByLabelText("Token (leitura; vazio para repositório público)"),
      "ghp_x",
    );
    await user.type(within(form).getByLabelText("Sincronizar a cada (horas)"), "12");
    await user.click(within(form).getByRole("button", { name: "Salvar conector" }));

    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    expect(vi.mocked(client.POST).mock.calls[0][1]).toEqual({
      params: { path: { base_id: "b1" } },
      body: {
        kind: "github",
        name: "Docs",
        settings: { repo: "acme/docs", path: "docs" },
        secret: { token: "ghp_x" },
        sync_every_hours: 12,
      },
    });
  });

  it("editar sem digitar segredo mantém o salvo", async () => {
    mockGet("owner");
    const user = userEvent.setup();
    render(<KnowledgeConnectors baseId="b1" />, { wrapper });
    const row = await screen.findByRole("listitem", { name: "Conector Documentação" });
    expect(row).toHaveTextContent("6 documento(s)");
    await user.click(within(row).getByRole("button", { name: "Editar" }));
    await user.click(screen.getByRole("button", { name: "Salvar conector" }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    const body = (vi.mocked(client.PUT).mock.calls[0][1] as { body: { secret: unknown } }).body;
    expect(body.secret).toBeNull();
  });

  it("editor sincroniza mas não cadastra nem remove", async () => {
    mockGet("editor");
    const user = userEvent.setup();
    render(<KnowledgeConnectors baseId="b1" />, { wrapper });
    const row = await screen.findByRole("listitem", { name: "Conector Documentação" });
    expect(screen.queryByRole("button", { name: "Novo conector" })).toBeNull();
    expect(within(row).queryByRole("button", { name: "Remover" })).toBeNull();
    await user.click(within(row).getByRole("button", { name: "Sincronizar" }));
    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    expect(vi.mocked(client.POST).mock.calls[0][0]).toBe(
      "/api/v1/knowledge-bases/{base_id}/connectors/{connector_id}/sync",
    );
  });
});
