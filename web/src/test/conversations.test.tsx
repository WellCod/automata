import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChannelsPage from "@/app/canais/page";
import ConversationsPage from "@/app/conversas/page";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import client from "@/lib/api/client";

const CONV = "cccccccc-cccc-cccc-cccc-cccccccccccc";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const summary = {
  id: CONV,
  channel_id: "ch",
  channel_name: "Atendimento",
  channel_kind: "whatsapp",
  user_id: "whatsapp:5511999990000",
  status: "human",
  assigned_to: null,
  assigned_label: null,
  handoff_reason: "pedido do cliente",
  last_message: "Quero falar com um atendente",
  last_message_at: "2026-11-13T12:00:00Z",
};

const detail = {
  ...summary,
  messages: [
    {
      id: "m1",
      direction: "in",
      author: "customer",
      author_label: null,
      text: "Quero falar com um atendente",
      status: "received",
      error: null,
      created_at: "2026-11-13T12:00:00Z",
    },
    {
      id: "m2",
      direction: "out",
      author: "attendant:u1",
      author_label: "ana@exemplo.com",
      text: "Oi, sou a Ana",
      status: "failed",
      error: "WhatsApp recusou (400): janela de 24 horas",
      created_at: "2026-11-13T12:01:00Z",
    },
  ],
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Conversas", () => {
  it("abre a conversa da fila, mostra a falha de envio e responde pelo canal", async () => {
    vi.mocked(client.GET).mockImplementation((async (path: string) =>
      path === "/api/v1/conversations" ? { data: [summary] } : { data: detail }) as never);
    vi.mocked(client.POST).mockResolvedValue({ data: detail } as never);
    wrap(<ConversationsPage />);

    await userEvent.click(await screen.findByRole("button", { name: /whatsapp:5511999990000/ }));
    expect(await screen.findByText("Motivo da passagem: pedido do cliente")).toBeInTheDocument();
    expect(screen.getByText(/ana@exemplo.com/)).toBeInTheDocument();
    expect(screen.getByText(/Não enviada: WhatsApp recusou/)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Responder pelo canal"), "Pode me passar o pedido?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/conversations/{conversation_id}/reply", {
        params: { path: { conversation_id: CONV } },
        body: { text: "Pode me passar o pedido?" },
      }),
    );
  });
});

describe("Canais", () => {
  it("cria um canal do Slack com os campos da credencial do Slack", async () => {
    vi.mocked(client.GET).mockImplementation((async (
      path: string,
      opts: { params?: { query?: { kind?: string } } },
    ) =>
      path === "/api/v1/channels"
        ? { data: [] }
        : {
            data: {
              items:
                opts?.params?.query?.kind === "agent"
                  ? [{ id: "a1", name: "Atendimento", kind: "agent" }]
                  : [],
            },
          }) as never);
    vi.mocked(client.POST).mockResolvedValue({ data: {} } as never);
    wrap(<ChannelsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Novo canal" }));
    await userEvent.selectOptions(screen.getByLabelText("Tipo"), "slack");
    expect(screen.queryByLabelText("ID do número")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Nome"), "Slack interno");
    await userEvent.selectOptions(await screen.findByLabelText("Quem responde"), "a1");
    await userEvent.type(screen.getByLabelText("Bot token (xoxb-…)"), "xoxb-1");
    await userEvent.type(screen.getByLabelText("Signing secret"), "s3");
    await userEvent.click(screen.getByRole("button", { name: "Salvar canal" }));
    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/channels", {
        body: expect.objectContaining({
          kind: "slack",
          name: "Slack interno",
          config_id: "a1",
          credentials: { bot_token: "xoxb-1", signing_secret: "s3" },
        }),
      }),
    );
  });
});
