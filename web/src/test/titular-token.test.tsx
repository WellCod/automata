import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { isOverdue, RequestsTable } from "@/components/data-subjects-panel";
import { MyDataPanel } from "@/components/my-data-panel";
import { EVENT_LABELS } from "@/lib/alert-events";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const base = {
  id: "11111111-1111-1111-1111-111111111111",
  kind: "export",
  subject: "carla",
  subject_hash: "a".repeat(64),
  status: "done",
  requested_by: "integration:abc",
  source: "integration",
  counts: { sessions: 1 },
  error: null,
  expires_at: "2026-11-11T12:00:00Z",
  created_at: "2026-11-04T12:00:00Z",
  due_at: "2026-11-19T12:00:00Z",
  finished_at: "2026-11-04T12:00:01Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("pedidos do titular", () => {
  it("mostra origem e prazo e destaca o vencido", () => {
    const late = {
      ...base,
      id: "22222222-2222-2222-2222-222222222222",
      status: "pending",
      due_at: "2026-01-01T00:00:00Z",
      source: "self",
    };
    render(<RequestsTable requests={[base, late] as never} />);
    const [, first, second] = screen.getAllByRole("row");
    expect(within(first!).getByText("Integração")).toBeInTheDocument();
    expect(within(second!).getByText("vencido")).toBeInTheDocument();
    expect(isOverdue(late as never)).toBe(true);
    expect(isOverdue(base as never)).toBe(false);
  });

  it("eventos de aviso do titular têm rótulo", () => {
    expect(EVENT_LABELS["data_subject.failed"]).toBe("Pedido de titular falhou");
    expect(EVENT_LABELS["data_subject.due"]).toBe("Pedido de titular perto do prazo");
  });
});

describe("meus dados", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockImplementation((async (path: string) => {
      if (path === "/api/v1/me/data")
        return { data: { user_id: "u1", counts: { sessions: 3 }, total: 3 }, error: undefined };
      if (path === "/api/v1/me/data/requests")
        return { data: [{ ...base, source: "self" }], error: undefined };
      if (path === "/api/v1/me")
        return { data: { id: "u1", email: "carla@empresa.com", role: "viewer" }, error: undefined };
      return { data: undefined, error: { detail: "x" } };
    }) as never);
  });

  it("baixa pelo caminho do próprio usuário e apaga só com o e-mail", async () => {
    vi.mocked(client.POST).mockResolvedValue({
      data: base,
      error: undefined,
      response: { status: 202 },
    } as never);
    const user = userEvent.setup();
    render(<MyDataPanel />, { wrapper });
    expect(await screen.findByText("Conversas")).toBeInTheDocument();
    const link = await screen.findByRole("link", { name: "Baixar" });
    expect(link).toHaveAttribute("href", `/api/api/v1/me/data/requests/${base.id}/download`);

    await user.click(screen.getByRole("button", { name: "Apagar meus dados" }));
    const apagar = screen.getByRole("button", { name: "Apagar definitivamente" });
    const box = await screen.findByLabelText(/Digite o seu e-mail \(carla@empresa.com\)/);
    await user.type(box, "outra@x.com");
    expect(apagar).toBeDisabled();
    await user.clear(box);
    await user.type(box, "Carla@Empresa.com");
    await user.click(apagar);
    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/me/data/erase", {
        body: { confirm: "Carla@Empresa.com" },
      }),
    );
  });
});
