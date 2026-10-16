import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_GUARDRAILS,
  type Guardrails,
  GuardrailsEditor,
  withDefaults,
} from "@/components/guardrails-editor";
import { RunsPanel } from "@/components/runs-panel";
import { TestPanel } from "@/components/test-panel";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

function Harness({ onValue }: { onValue: (v: Guardrails) => void }) {
  const [value, setValue] = useState<Guardrails>(DEFAULT_GUARDRAILS);
  return (
    <GuardrailsEditor
      value={value}
      onChange={(v) => {
        setValue(v);
        onValue(v);
      }}
    />
  );
}

describe("GuardrailsEditor", () => {
  it("começa desligado e liga dados pessoais em modo bloquear só com CPF", async () => {
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    expect(screen.queryByRole("group", { name: "Tipos de dado na entrada" })).toBeNull();

    await userEvent.selectOptions(screen.getByLabelText("Dados pessoais na mensagem"), "block");
    const tipos = screen.getByRole("group", { name: "Tipos de dado na entrada" });
    for (const nome of ["CNPJ", "Cartão", "E-mail", "Telefone"]) {
      await userEvent.click(screen.getAllByRole("checkbox", { name: nome })[0]);
    }
    expect(tipos).toBeInTheDocument();
    expect(onValue).toHaveBeenLastCalledWith(
      expect.objectContaining({ pii: { mode: "block", types: ["cpf"] } }),
    );
  });

  it("termos por linha, limite vazio vira sem limite e aviso da saída em stream", async () => {
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    const topicos = screen.getByLabelText("Tópicos proibidos");
    fireEvent.blur(topicos, { target: { value: "política\n\n  futebol  \n" } });
    expect(onValue).toHaveBeenLastCalledWith(
      expect.objectContaining({ blocked_topics: ["política", "futebol"] }),
    );

    const max = screen.getByLabelText("Tamanho máximo da mensagem (caracteres)");
    fireEvent.change(max, { target: { value: "2000" } });
    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ max_input_chars: 2000 }));
    fireEvent.change(max, { target: { value: "" } });
    expect(onValue).toHaveBeenLastCalledWith(expect.objectContaining({ max_input_chars: null }));

    expect(screen.getByText(/o texto já foi entregue quando a regra roda/)).toBeInTheDocument();
  });

  it("completa payload antigo sem seções", () => {
    const g = withDefaults({ prompt_injection: true } as Partial<Guardrails>);
    expect(g.pii?.mode).toBe("off");
    expect(g.output?.pii).toBe(false);
    expect(g.prompt_injection).toBe(true);
  });
});

function sse(eventType: string, data: object): string {
  return `event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`;
}

describe("TestPanel com guardrail", () => {
  it("mostra a mensagem de bloqueio como resposta, com o motivo, sem erro", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(c) {
        c.enqueue(encoder.encode(sse("RunStarted", { session_id: "s1", run_id: "r1" })));
        c.enqueue(
          encoder.encode(
            sse("RunError", {
              content: "Não posso ajudar com isso.",
              error_type: "input_check_error",
              error_id: "pii_detected",
              additional_data: { rule: "pii_detected", types: ["cpf"] },
            }),
          ),
        );
        c.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, body } as unknown as Response));
    render(<TestPanel agentId="a1" defaultOpen />);
    await userEvent.type(screen.getByPlaceholderText(/Digite uma mensagem/i), "meu cpf");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => expect(screen.getByText("Não posso ajudar com isso.")).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent(
      "bloqueado pelo guardrail · Dados pessoais",
    );
    expect(screen.queryByText("Erro ao executar agente.")).toBeNull();
  });
});

describe("RunsPanel", () => {
  it("mostra run bloqueado com o motivo", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: {
        items: [
          {
            id: "1",
            agent_config_id: "a1",
            user_id: "ana",
            run_id: null,
            status: "blocked",
            duration_ms: 3,
            error: "Não posso ajudar com isso.",
            blocked_by: "prompt_injection",
            created_at: "2026-10-16T12:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      },
      error: undefined,
    } as never);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <RunsPanel agentId="a1" />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Bloqueado")).toBeInTheDocument();
    expect(screen.getByText("Injeção de prompt")).toBeInTheDocument();
  });
});
