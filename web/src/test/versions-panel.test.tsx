import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VersionsPanel } from "@/components/versions-panel";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn() },
}));

import client from "@/lib/api/client";

const AGENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

const basePayload = {
  schema_version: 2 as const,
  model_id: "claude-sonnet-4-6",
  instructions: { persona: "A", situation: "", tone: "", objective: "", guardrails: "" },
  mcp_servers: [],
  capabilities: { extended_thinking: false, structured_output: false, vision: false },
  metadata: {},
};

const mockVersions = [
  {
    id: "v3",
    version_number: 3,
    label: null,
    status: "draft",
    author: "panel",
    created_at: "2025-06-03T10:00:00Z",
    payload: { ...basePayload, model_id: "claude-opus-4-7" },
  },
  {
    id: "v2",
    version_number: 2,
    label: null,
    status: "published",
    author: "panel",
    created_at: "2025-06-02T10:00:00Z",
    payload: basePayload,
  },
  {
    id: "v1",
    version_number: 1,
    label: null,
    status: "published",
    author: "panel",
    created_at: "2025-06-01T10:00:00Z",
    payload: basePayload,
  },
];

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>;
}

describe("VersionsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.GET).mockResolvedValue({ data: mockVersions, error: undefined } as never);
    vi.mocked(client.POST).mockResolvedValue({
      data: {
        id: "v2",
        version_number: 2,
        label: null,
        status: "published",
        author: "panel",
        created_at: "2025-06-02T10:00:00Z",
      },
      error: undefined,
    } as never);
  });

  it("exibe a lista de versões", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("v3")).toBeInTheDocument();
    });
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
  });

  it("exibe botão publicar quando há rascunho", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /publicar/i })).toBeInTheDocument();
    });
  });

  it("não exibe botão publicar sem rascunho", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: [mockVersions[1], mockVersions[2]],
      error: undefined,
    } as never);
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("v2")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /publicar/i })).not.toBeInTheDocument();
  });

  it("exibe diff de campos alterados no rascunho", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/modelo:/i)).toBeInTheDocument();
    });
  });

  it("exibe botão reverter em versão publicada anterior", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /reverter/i })).toBeInTheDocument();
    });
  });

  it("chama publish ao clicar em publicar rascunho", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /publicar/i })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: /^publicar$/i }));
    expect(client.POST).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /confirmar publicação/i }));
    await waitFor(() => {
      expect(client.POST).toHaveBeenCalledWith(
        "/api/v1/configs/{config_id}/publish",
        expect.objectContaining({ params: { path: { config_id: AGENT_ID } } }),
      );
    });
  });

  it("chama rollback ao clicar em reverter", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /reverter/i })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: /reverter/i }));
    expect(client.POST).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /confirmar reversão/i }));
    await waitFor(() => {
      expect(client.POST).toHaveBeenCalledWith(
        "/api/v1/configs/{config_id}/rollback",
        expect.objectContaining({
          params: { path: { config_id: AGENT_ID } },
          body: { version_id: "v1" },
        }),
      );
    });
  });

  it("cancelar a confirmação não publica", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await userEvent.click(await screen.findByRole("button", { name: /^publicar$/i }));
    await userEvent.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(client.POST).not.toHaveBeenCalled();
  });

  it("avisa que alterações não salvas ficam fora da publicação", async () => {
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" hasUnsavedChanges />, {
      wrapper,
    });
    await userEvent.click(await screen.findByRole("button", { name: /^publicar$/i }));
    expect(screen.getByText(/alterações não salvas/i)).toBeInTheDocument();
  });

  it("usa a versão ativa do agente, não a publicada mais recente", async () => {
    // depois de reverter para v1, v2 continua publicada mas não está ativa
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v1" />, { wrapper });
    const v1 = (await screen.findByText("v1")).closest("li")!;
    const v2 = screen.getByText("v2").closest("li")!;
    expect(within(v1).getByText(/ativa/i)).toBeInTheDocument();
    expect(within(v1).queryByRole("button", { name: /reverter/i })).not.toBeInTheDocument();
    expect(within(v2).getByRole("button", { name: /reverter/i })).toBeInTheDocument();
  });

  it("exibe estado de lista vazia", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: [], error: undefined } as never);
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Nenhuma versão salva.")).toBeInTheDocument();
    });
  });

  it("exibe erro quando API falha", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: undefined,
      error: { detail: "erro" },
    } as never);
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Erro ao carregar versões.")).toBeInTheDocument();
    });
  });
});

describe("VersionsPanel com suíte", () => {
  const settings = (overrides: object) => ({
    require_passing_evals: true,
    draft_version_id: "v3",
    draft_run: null,
    can_publish: false,
    reason: "a suíte ainda não rodou no rascunho atual",
    ...overrides,
  });

  function mockGet(evalSettings: object) {
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      const data: Record<string, unknown> = {
        "/api/v1/configs/{config_id}/versions": mockVersions,
        "/api/v1/configs/{config_id}/eval-settings": evalSettings,
        "/api/v1/configs/{config_id}/eval-cases": [{ id: "c1" }],
      };
      return { data: data[path], error: undefined } as never;
    });
  }

  beforeEach(() => vi.clearAllMocks());

  it("gate bloqueia o publicar enquanto a suíte não passa no rascunho", async () => {
    mockGet(settings({}));
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" suite />, { wrapper });
    const status = await screen.findByRole("status", { name: "Suíte do rascunho" });
    expect(status).toHaveTextContent("A suíte ainda não rodou no rascunho atual.");
    expect(status).toHaveTextContent("Publicação bloqueada pelo gate");
    expect(screen.getByRole("button", { name: "Publicar" })).toBeDisabled();
  });

  it("suíte verde libera e mostra o resultado", async () => {
    mockGet(
      settings({
        can_publish: true,
        reason: null,
        draft_run: { status: "completed", passed: 3, total: 3 },
      }),
    );
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" suite />, { wrapper });
    const status = await screen.findByRole("status", { name: "Suíte do rascunho" });
    expect(status).toHaveTextContent("Suíte no rascunho: 3 de 3 passaram.");
    expect(status).not.toHaveTextContent("bloqueada");
    await waitFor(() => expect(screen.getByRole("button", { name: "Publicar" })).toBeEnabled());
  });

  it("sem a prop suite (workflow) não consulta a suíte", async () => {
    mockGet(settings({}));
    render(<VersionsPanel agentId={AGENT_ID} currentVersionId="v2" />, { wrapper });
    await screen.findByRole("button", { name: "Publicar" });
    const paths = vi.mocked(client.GET).mock.calls.map((c) => c[0]);
    expect(paths).toEqual(["/api/v1/configs/{config_id}/versions"]);
    expect(screen.queryByRole("status", { name: "Suíte do rascunho" })).toBeNull();
  });
});
