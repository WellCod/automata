import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TestPanel } from "@/components/test-panel";

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

function sseChunk(eventType: string, data: object): string {
  return `event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`;
}

describe("TestPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza o botão de abrir chat", () => {
    render(<TestPanel agentId="agent-1" />);
    expect(screen.getByRole("button", { name: /abrir chat/i })).toBeInTheDocument();
  });

  it("exibe área de chat ao clicar em abrir", async () => {
    render(<TestPanel agentId="agent-1" />);
    await userEvent.click(screen.getByRole("button", { name: /abrir chat/i }));
    expect(screen.getByPlaceholderText(/Digite uma mensagem/i)).toBeInTheDocument();
  });

  it("envia mensagem e exibe resposta do agente via SSE", async () => {
    const stream = makeStream([
      sseChunk("RunStarted", { session_id: "sess-1", run_id: "run-1" }),
      sseChunk("RunContent", { content: "Olá" }),
      sseChunk("RunContent", { content: ", tudo bem?" }),
      sseChunk("RunCompleted", {}),
    ]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: stream } as unknown as Response),
    );

    render(<TestPanel agentId="agent-1" />);
    await userEvent.click(screen.getByRole("button", { name: /abrir chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/Digite uma mensagem/i), "Oi");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => {
      expect(screen.getByText("Olá, tudo bem?")).toBeInTheDocument();
    });
    expect(screen.getByText("Oi")).toBeInTheDocument();
  });

  it("chama /api/agents/{id}/runs com FormData", async () => {
    const stream = makeStream([sseChunk("RunCompleted", {})]);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, body: stream } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(<TestPanel agentId="abc-123" />);
    await userEvent.click(screen.getByRole("button", { name: /abrir chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/Digite uma mensagem/i), "Teste");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/agents/abc-123/runs");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it("envia factory_input com version_id ao testar rascunho", async () => {
    const stream = makeStream([sseChunk("RunCompleted", {})]);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, body: stream } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(<TestPanel agentId="abc-123" draftVersionId="draft-uuid" />);
    await userEvent.click(screen.getByRole("button", { name: /abrir chat/i }));
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.type(screen.getByPlaceholderText(/Digite uma mensagem/i), "Teste rascunho");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const form = fetchMock.mock.calls[0][1].body as FormData;
    const factoryInput = form.get("factory_input") as string;
    expect(JSON.parse(factoryInput)).toEqual({ version_id: "draft-uuid" });
  });

  it("exibe erro quando fetch falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, body: null } as unknown as Response),
    );

    render(<TestPanel agentId="agent-1" />);
    await userEvent.click(screen.getByRole("button", { name: /abrir chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/Digite uma mensagem/i), "Teste");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => {
      expect(screen.getByText("Erro ao executar agente.")).toBeInTheDocument();
    });
  });

  it("limpa sessão ao clicar em limpar", async () => {
    const stream = makeStream([sseChunk("RunContent", { content: "Resposta" })]);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: stream } as unknown as Response),
    );

    render(<TestPanel agentId="agent-1" />);
    await userEvent.click(screen.getByRole("button", { name: /abrir chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/Digite uma mensagem/i), "Oi");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => expect(screen.getByText("Resposta")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /limpar/i }));
    expect(screen.getByText("Nenhuma mensagem ainda.")).toBeInTheDocument();
  });

  it("pausa para confirmação e retoma com a decisão", async () => {
    const tool = {
      tool_call_id: "call_1",
      tool_name: "crm_cancelar_assinatura",
      tool_args: { cliente_id: "7" },
      requires_confirmation: true,
      confirmed: null,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        body: makeStream([
          sseChunk("RunStarted", { session_id: "sess-9", run_id: "run-9" }),
          sseChunk("RunPaused", { run_id: "run-9", session_id: "sess-9", tools: [tool] }),
        ]),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        body: makeStream([
          sseChunk("RunContent", { content: "Assinatura cancelada." }),
          sseChunk("RunCompleted", {}),
        ]),
      } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(<TestPanel agentId="agent-1" defaultOpen />);
    await userEvent.type(screen.getByLabelText("Mensagem para o agente"), "cancela o 7");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    const dialog = await screen.findByRole("alertdialog", { name: /confirmação de ferramenta/i });
    expect(dialog).toHaveTextContent("crm_cancelar_assinatura");
    expect(screen.getByLabelText("Mensagem para o agente")).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Aprovar" }));
    await waitFor(() => expect(screen.getByText("Assinatura cancelada.")).toBeInTheDocument());

    const [url, opts] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/agents/agent-1/runs/run-9/continue");
    const form = opts.body as FormData;
    expect(form.get("session_id")).toBe("sess-9");
    expect(JSON.parse(form.get("tools") as string)).toEqual([{ ...tool, confirmed: true }]);
  });

  it("mostra a mensagem de RunError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: makeStream([sseChunk("RunError", { content: "servidor MCP 'crm' indisponível" })]),
      } as unknown as Response),
    );
    render(<TestPanel agentId="agent-1" defaultOpen />);
    await userEvent.type(screen.getByLabelText("Mensagem para o agente"), "oi");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("indisponível"));
  });
});
