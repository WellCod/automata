import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditLog } from "@/components/audit-log";
import { auditLabel, describeDetail } from "@/lib/audit-labels";

vi.mock("@/lib/api/client", () => ({ default: { GET: vi.fn() } }));

import client from "@/lib/api/client";

const CONFIG = "cccccccc-cccc-cccc-cccc-cccccccccccc";

function event(id: string, action: string, extra: object = {}) {
  return {
    id,
    created_at: "2026-11-10T12:00:00Z",
    actor: "u1",
    actor_label: "ana@exemplo.com",
    action,
    config_id: CONFIG,
    params: null,
    status_code: 201,
    ip: "10.0.0.1",
    request_id: "r",
    detail: null,
    ...extra,
  };
}

const page = {
  items: [
    event("e1", "POST /api/v1/configs/{config_id}/publish", {
      detail: { current_before: "v-1", current_after: "v-2" },
    }),
    event("e2", "POST /api/v1/configs/{config_id}/rollback", {
      status_code: 403,
      actor: "u2",
      actor_label: "bia@exemplo.com",
    }),
  ],
  next_cursor: "abc",
  configs: { [CONFIG]: { name: "Atendimento", kind: "agent" } },
  versions: { "v-1": 3, "v-2": 4 },
};

function renderLog(configId?: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuditLog configId={configId} />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.resetAllMocks());

describe("auditLabel e describeDetail", () => {
  it("traduz as ações conhecidas e cai num texto genérico nas outras", () => {
    expect(auditLabel("POST /api/v1/configs/{config_id}/canary/promote")).toBe("Promoveu canário");
    expect(auditLabel("POST /agents/{agent_id}/runs/{run_id}/continue")).toBe("Decidiu aprovação");
    expect(auditLabel("DELETE /api/v1/coisa/{id}")).toBe("Removeu coisa/{id}");
  });

  it("mostra a versão pelo número e só os campos que mudaram", () => {
    expect(describeDetail({ current_before: "a", current_after: "b" }, { a: 1, b: 2 })).toEqual([
      "vigente: v1 → v2",
    ]);
    expect(
      describeDetail(
        { before: { role: "editor", is_active: true }, after: { role: "viewer", is_active: true } },
        {},
      ),
    ).toEqual(["role: editor → viewer"]);
    expect(describeDetail({ before: null, after: { max_input_chars: 4000 } }, {})).toEqual([
      "criado",
    ]);
  });
});

describe("AuditLog", () => {
  it("lista com o nome do config, a versão, a recusa e carrega as mais antigas", async () => {
    vi.mocked(client.GET)
      .mockResolvedValueOnce({ data: page } as never)
      .mockResolvedValueOnce({
        data: {
          ...page,
          items: [event("e3", "PUT /api/v1/instance-guardrails")],
          next_cursor: null,
        },
      } as never);
    renderLog();

    expect(await screen.findByText("Publicou versão")).toBeInTheDocument();
    expect(screen.getByText("vigente: v3 → v4")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Atendimento" })[0]).toHaveAttribute(
      "href",
      `/agents/${CONFIG}`,
    );
    expect(screen.getByText("recusada (403)")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Mais antigas" }));
    expect(await screen.findByText("Mudou o piso de guardrails")).toBeInTheDocument();
    expect(vi.mocked(client.GET).mock.calls[1][1]).toMatchObject({
      params: { query: { cursor: "abc" } },
    });
  });

  it("filtra por quem fez ao clicar no nome", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: page } as never);
    renderLog();

    await userEvent.click(await screen.findByRole("button", { name: "bia@exemplo.com" }));
    await waitFor(() =>
      expect(vi.mocked(client.GET).mock.calls.at(-1)?.[1]).toMatchObject({
        params: { query: { actor: "u2" } },
      }),
    );
  });

  it("na aba Versões pede só o config, sem filtros", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: page } as never);
    renderLog(CONFIG);

    expect(await screen.findByText("Publicou versão")).toBeInTheDocument();
    expect(screen.queryByLabelText("Ação")).not.toBeInTheDocument();
    expect(vi.mocked(client.GET).mock.calls[0][1]).toMatchObject({
      params: { query: { config_id: CONFIG, limit: 10 } },
    });
  });
});
