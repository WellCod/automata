import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertsPage from "@/app/alertas/page";
import { QueuePanel } from "@/components/queue-panel";
import { ReconciliationPanel } from "@/components/reconciliation-panel";
import { DEFAULT_RUN, type RunControls, RunControlsEditor } from "@/components/run-controls-editor";
import { EVENT_LABELS } from "@/lib/alert-events";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const job = (over: Record<string, unknown>) => ({
  id: "j1",
  component_type: "agent",
  component_id: "a1",
  component_name: "cobranca",
  status: "failed",
  attempt: 1,
  max_attempts: 1,
  error: "ConnectError: provedor fora",
  user_id: null,
  created_at: "2026-11-04T12:00:00Z",
  completed_at: "2026-11-04T12:01:00Z",
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("fila", () => {
  it("mostra contagem e repete só o que falhou", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: {
        durable: true,
        counts: { queued: 2, running: 1, completed: 9, failed: 1, cancelled: 0, paused: 0 },
        oldest_queued_at: "2026-11-04T11:00:00Z",
        jobs: [job({}), job({ id: "j2", status: "completed", error: null })],
      },
      error: undefined,
    } as never);
    vi.mocked(client.POST).mockResolvedValue({ data: {}, error: undefined } as never);
    const user = userEvent.setup();
    render(<QueuePanel />, { wrapper });
    expect(await screen.findByText("provedor fora", { exact: false })).toBeInTheDocument();
    const [, failedRow, doneRow] = screen.getAllByRole("row");
    expect(within(doneRow!).queryByRole("button")).not.toBeInTheDocument();
    await user.click(within(failedRow!).getByRole("button", { name: "Repetir" }));
    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/queue/jobs/{job_id}/requeue", {
        params: { path: { job_id: "j1" } },
      }),
    );
  });

  it("fila em memória explica que não há o que mostrar", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: { durable: false, counts: {}, oldest_queued_at: null, jobs: [] },
      error: undefined,
    } as never);
    render(<QueuePanel />, { wrapper });
    expect(await screen.findByText(/fila durável está desligada/)).toBeInTheDocument();
  });
});

describe("conciliação", () => {
  it("destaca o dia fechado acima do limite", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: {
        providers: ["anthropic"],
        alert_percent: 20,
        rows: [
          {
            provider: "anthropic",
            day: "2026-11-03",
            reported_usd: 10,
            estimated_usd: 6,
            diff_usd: 4,
            diff_percent: 40,
            closed: true,
            fetched_at: "2026-11-04T12:00:00Z",
          },
          {
            provider: "anthropic",
            day: "2026-11-04",
            reported_usd: 1,
            estimated_usd: 0.5,
            diff_usd: 0.5,
            diff_percent: 50,
            closed: false,
            fetched_at: "2026-11-04T12:00:00Z",
          },
        ],
      },
      error: undefined,
    } as never);
    render(<ReconciliationPanel />, { wrapper });
    const closed = await screen.findByText("+40%");
    expect(closed).toHaveClass("text-destructive");
    expect(screen.getByText("+50%")).not.toHaveClass("text-destructive");
    expect(screen.getByText("em aberto")).toBeInTheDocument();
  });

  it("sem chave admin a seção não aparece", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: { providers: [], alert_percent: 20, rows: [] },
      error: undefined,
    } as never);
    const { container } = render(<ReconciliationPanel />, { wrapper });
    await waitFor(() => expect(client.GET).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});

describe("retry no controle do run e aviso por e-mail", () => {
  it("liga a repetição e avisa do risco", async () => {
    let last: RunControls = DEFAULT_RUN;
    function Harness() {
      const [value, setValue] = useState<RunControls>(DEFAULT_RUN);
      return (
        <RunControlsEditor
          value={value}
          onChange={(v) => {
            last = v;
            setValue(v);
          }}
          modelId="claude-haiku-4-5"
          capabilities={{ extended_thinking: false, structured_output: false, vision: false }}
        />
      );
    }
    const user = userEvent.setup();
    vi.mocked(client.GET).mockResolvedValue({ data: {}, error: undefined } as never);
    render(<Harness />, { wrapper });
    await user.selectOptions(screen.getByLabelText("Repetições do run em background"), "1");
    expect(last.background_retries).toBe(1);
    expect(screen.getByText(/pagamento ou envio de mensagem não/)).toBeInTheDocument();
  });

  it("cadastra destino por e-mail sem mostrar segredo", async () => {
    vi.mocked(client.GET).mockImplementation((async (path: string) => {
      if (path === "/api/v1/alert-destinations/channels")
        return { data: { webhook: true, email: true }, error: undefined };
      return { data: [], error: undefined };
    }) as never);
    vi.mocked(client.POST).mockResolvedValue({
      data: {
        id: "d1",
        name: "financeiro",
        kind: "email",
        host: "e-mail",
        emails: ["fin@empresa.com"],
        events: ["job.failed"],
        created_by: "owner",
        last_status: null,
        last_at: null,
        created_at: "2026-11-04T12:00:00Z",
        secret: "",
      },
      error: undefined,
    } as never);
    const user = userEvent.setup();
    render(<AlertsPage />, { wrapper });
    await user.type(screen.getByPlaceholderText("#operacao no Slack"), "financeiro");
    await screen.findByRole("option", { name: "E-mail" });
    await user.selectOptions(screen.getByDisplayValue("Webhook"), "email");
    await user.type(
      screen.getByPlaceholderText(/financeiro@empresa.com/),
      "fin@empresa.com, x@y.com",
    );
    await user.click(screen.getByRole("button", { name: "Cadastrar destino" }));
    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    const [, opts] = vi.mocked(client.POST).mock.calls[0] as unknown as [string, { body: unknown }];
    expect(opts.body).toMatchObject({
      name: "financeiro",
      kind: "email",
      emails: ["fin@empresa.com", "x@y.com"],
    });
    expect(screen.queryByRole("alertdialog", { name: "Segredo do destino" })).toBeNull();
    expect(EVENT_LABELS["job.failed"]).toBe("Run em background falhou");
  });
});
