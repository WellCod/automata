import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CanaryPanel } from "@/components/canary-panel";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

const ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

const payload = {
  schema_version: 2 as const,
  model_id: "claude-sonnet-4-6",
  instructions: { persona: "", situation: "", tone: "", objective: "", guardrails: "" },
  mcp_servers: [],
  capabilities: { extended_thinking: false, structured_output: false, vision: false },
  metadata: {},
};

function version(id: string, n: number, status: "draft" | "published") {
  return {
    id,
    version_number: n,
    label: null,
    status,
    author: "panel",
    created_at: "2026-11-01T10:00:00Z",
    payload,
  };
}

const versions = [version("v3", 3, "draft"), version("v2", 2, "published")];

function stats(id: string, n: number, extra: object = {}) {
  return {
    version_id: id,
    version_number: n,
    runs: 40,
    errors: 2,
    error_rate: 0.05,
    p50_ms: 900,
    p95_ms: 2400,
    avg_cost: 0.0031,
    suite: null,
    ...extra,
  };
}

const inactive = { active: false, percent: null, started_at: null, current: null, canary: null };
const active = {
  active: true,
  percent: 20,
  started_at: "2026-11-10T10:00:00Z",
  current: stats("v2", 2),
  canary: stats("v4", 4, {
    runs: 10,
    errors: 0,
    error_rate: 0,
    suite: { status: "completed", total: 5, passed: 5, failed: 0, created_at: "x" },
  }),
};

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CanaryPanel configId={ID} versions={versions} currentVersionId="v2" draftVersionId="v3" />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.resetAllMocks());

describe("CanaryPanel", () => {
  it("liga o canário a partir do rascunho com o percentual escolhido", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: inactive } as never);
    vi.mocked(client.POST).mockResolvedValue({ data: active } as never);
    renderPanel();

    const percent = await screen.findByRole("spinbutton");
    await userEvent.clear(percent);
    await userEvent.type(percent, "20");
    await userEvent.click(screen.getByRole("button", { name: "Ligar canário" }));

    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/configs/{config_id}/canary", {
        params: { path: { config_id: ID } },
        body: { percent: 20, version_id: null },
      }),
    );
  });

  it("mostra a comparação e promove depois de confirmar", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: active } as never);
    vi.mocked(client.POST).mockResolvedValue({ data: inactive } as never);
    renderPanel();

    expect(await screen.findByText("Canário: v4 em 20% das conversas")).toBeInTheDocument();
    expect(screen.getByText("v2 (vigente)")).toBeInTheDocument();
    expect(screen.getByText("5 de 5")).toBeInTheDocument();
    expect(screen.getAllByText("2,4 s")).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: "Promover v4" }));
    expect(client.POST).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar promoção" }));
    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/configs/{config_id}/canary/promote", {
        params: { path: { config_id: ID } },
      }),
    );
  });

  it("ajusta o percentual e desliga", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: active } as never);
    vi.mocked(client.PATCH).mockResolvedValue({ data: { ...active, percent: 40 } } as never);
    vi.mocked(client.DELETE).mockResolvedValue({ data: inactive } as never);
    renderPanel();

    const percent = await screen.findByRole("spinbutton");
    await userEvent.clear(percent);
    await userEvent.type(percent, "40");
    await userEvent.click(screen.getByRole("button", { name: "Ajustar" }));
    await waitFor(() =>
      expect(client.PATCH).toHaveBeenCalledWith("/api/v1/configs/{config_id}/canary", {
        params: { path: { config_id: ID } },
        body: { percent: 40 },
      }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Desligar" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    await waitFor(() => expect(client.DELETE).toHaveBeenCalled());
  });
});
