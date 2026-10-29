import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IntegrationsPage from "@/app/integracoes/page";
import { KeyRotationView, type KeyRotationStatus } from "@/components/key-rotation-panel";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const quiet: KeyRotationStatus = {
  jwt: { current_kid: "a1b2", previous_kid: null, tokens_on_previous: 0, tokens_without_kid: 0 },
  secrets: {
    configured: true,
    previous_configured: false,
    pending: { mcp_server: 0, eval_schedule: 0, alert_destination: 0, knowledge_connector: 0 },
  },
  done: true,
};

describe("estado da rotação de chaves", () => {
  it("sem troca em andamento", () => {
    render(<KeyRotationView status={quiet} />);
    expect(screen.getByRole("status")).toHaveTextContent("Nenhuma troca em andamento.");
    expect(screen.queryByText(/rotate_secrets/)).toBeNull();
  });

  it("troca em andamento aponta tokens e segredos na chave anterior", () => {
    render(
      <KeyRotationView
        status={{
          jwt: {
            current_kid: "novo",
            previous_kid: "velho",
            tokens_on_previous: 2,
            tokens_without_kid: 1,
          },
          secrets: {
            configured: true,
            previous_configured: true,
            pending: { ...quiet.secrets.pending, mcp_server: 3 },
          },
          done: false,
        }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Troca em andamento");
    const jwt = screen.getByRole("region", { name: "Chave JWT" });
    expect(within(jwt).getByText("velho")).toBeInTheDocument();
    expect(within(jwt).getByRole("link", { name: "Integrações" })).toHaveAttribute(
      "href",
      "/integracoes",
    );
    const secrets = screen.getByRole("region", { name: "Chave dos segredos" });
    expect(
      within(secrets).getByText("Servidores MCP na chave anterior").nextSibling,
    ).toHaveTextContent("3");
    expect(secrets).toHaveTextContent("python -m app.rotate_secrets");
  });

  it("troca terminada manda tirar as variáveis anteriores", () => {
    render(<KeyRotationView status={{ ...quiet, jwt: { ...quiet.jwt, previous_kid: "velho" } }} />);
    expect(screen.getByRole("status")).toHaveTextContent("JWT_PREVIOUS_PUBLIC_KEY");
  });
});

describe("integrações na chave anterior", () => {
  beforeEach(() => vi.clearAllMocks());

  it("marca só o token ativo fora da chave atual", async () => {
    const base = {
      agent_ids: [],
      team_ids: [],
      eval_ids: [],
      created_by: "owner",
      created_at: "2026-10-01T10:00:00Z",
      expires_at: "2099-01-01T00:00:00Z",
      revoked_at: null,
    };
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/integrations")
        return {
          data: [
            { ...base, id: "1", name: "crm", on_current_key: false },
            { ...base, id: "2", name: "erp", on_current_key: true },
            {
              ...base,
              id: "3",
              name: "antigo",
              on_current_key: false,
              revoked_at: "2026-10-02T10:00:00Z",
            },
          ],
          error: undefined,
        } as never;
      return { data: { items: [] }, error: undefined } as never;
    });
    render(<IntegrationsPage />, { wrapper });
    const list = await screen.findByRole("list", { name: "Integrações" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("chave anterior");
    expect(rows[1]).not.toHaveTextContent("chave anterior");
    expect(rows[2]).not.toHaveTextContent("chave anterior");
  });
});
