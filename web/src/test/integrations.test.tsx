import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IntegrationsPage from "@/app/integracoes/page";
import { mcpSnippet } from "@/lib/mcp-snippet";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("integrações", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/integrations") return { data: [], error: undefined } as never;
      const kind = (opts as { params: { query: { kind: string } } }).params.query.kind;
      const items = kind === "agent" ? [{ id: "a1", name: "Cobrança", description: "x" }] : [];
      return { data: { items, total: items.length }, error: undefined } as never;
    });
  });

  it("monta configuração MCP com url e token", () => {
    const parsed = JSON.parse(mcpSnippet("https://api.x/mcp", "tok"));
    expect(parsed.mcpServers.automata).toEqual({
      url: "https://api.x/mcp",
      headers: { Authorization: "Bearer tok" },
    });
  });

  it("emite token para os agentes marcados e mostra uma vez", async () => {
    vi.mocked(client.POST).mockResolvedValue({
      data: {
        id: "i1",
        name: "zendesk",
        agent_ids: ["a1"],
        team_ids: [],
        created_by: "owner",
        created_at: "2026-10-15T00:00:00Z",
        expires_at: "2026-11-14T00:00:00Z",
        revoked_at: null,
        token: "jwt-secreto",
        mcp_url: "https://api.x/mcp",
      },
      error: undefined,
    } as never);
    const user = userEvent.setup();
    render(<IntegrationsPage />, { wrapper });

    const emitir = screen.getByRole("button", { name: "Emitir token" });
    expect(emitir).toBeDisabled();
    await user.type(screen.getByLabelText("Sistema consumidor"), "zendesk");
    await user.click(await screen.findByRole("checkbox", { name: "Cobrança" }));
    await user.click(emitir);

    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    expect(vi.mocked(client.POST).mock.calls[0][1]).toEqual({
      body: { name: "zendesk", agent_ids: ["a1"], team_ids: [], expires_in_days: 30 },
    });
    const dialog = await screen.findByRole("alertdialog", { name: /token emitido/i });
    expect(dialog).toHaveTextContent("jwt-secreto");
    expect(dialog).toHaveTextContent("https://api.x/mcp");

    await user.click(screen.getByRole("button", { name: "Já copiei" }));
    expect(screen.queryByText("jwt-secreto")).not.toBeInTheDocument();
  });
});
