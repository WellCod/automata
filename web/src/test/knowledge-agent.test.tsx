import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { type KnowledgeBinding, KnowledgeSelector } from "@/components/knowledge-selector";
import { TestPanel } from "@/components/test-panel";
import { mergeSources, sourcesFromTool } from "@/lib/knowledge-sources";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

const rh = {
  id: "kb1",
  name: "Políticas de RH",
  slug: "rh",
  description: "Férias e benefícios",
  embedder: "voyage",
  embedder_model: "voyage-3.5",
  dimensions: 1024,
  chunk_size: 2000,
  embedding_tokens: 1200,
  embedding_cost: 0.000072,
  updated_by: "e",
  created_at: "2026-10-16T12:00:00Z",
  updated_at: "2026-10-16T12:00:00Z",
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function Harness({
  initial,
  onValue,
}: {
  initial: KnowledgeBinding[];
  onValue: (v: KnowledgeBinding[]) => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <KnowledgeSelector
      value={value}
      onChange={(v) => {
        setValue(v);
        onValue(v);
      }}
    />
  );
}

const busca = JSON.stringify({
  base: "Políticas de RH",
  trechos: [
    { documento: "ferias", fonte: "ferias.pdf", content_id: "c1", texto: "trinta dias" },
    { documento: "ferias", fonte: "ferias.pdf", content_id: "c1", texto: "outro trecho" },
    { documento: "reembolso", fonte: "reembolso.md", content_id: "c2", texto: "nota" },
  ],
});

describe("KnowledgeSelector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.GET).mockResolvedValue({ data: [rh], error: undefined } as never);
  });

  it("liga a base com 5 trechos e ajusta o limite", async () => {
    const onValue = vi.fn();
    render(<Harness initial={[]} onValue={onValue} />, { wrapper });
    await userEvent.click(await screen.findByRole("checkbox", { name: /políticas de rh/i }));
    expect(onValue).toHaveBeenLastCalledWith([{ base_id: "kb1", max_results: 5 }]);

    const max = screen.getByLabelText("Trechos por busca em Políticas de RH");
    // campo limpo vira 1 a cada tecla; o valor final é o que importa
    fireEvent.change(max, { target: { value: "8" } });
    expect(onValue).toHaveBeenLastCalledWith([{ base_id: "kb1", max_results: 8 }]);
  });

  it("avisa sobre base ligada que não existe mais", async () => {
    const onValue = vi.fn();
    render(<Harness initial={[{ base_id: "sumiu", max_results: 5 }]} onValue={onValue} />, {
      wrapper,
    });
    expect(await screen.findByText(/não existem mais/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /remover/i }));
    expect(onValue).toHaveBeenLastCalledWith([]);
  });
});

describe("fontes da busca", () => {
  it("extrai documentos sem repetir e ignora outras tools", () => {
    const sources = sourcesFromTool({ tool_name: "buscar_rh", result: busca });
    expect(mergeSources([], sources).map((s) => s.documento)).toEqual(["ferias", "reembolso"]);
    expect(sourcesFromTool({ tool_name: "crm_buscar_cliente", result: busca })).toEqual([]);
    expect(sourcesFromTool({ tool_name: "buscar_rh", result: "não é json" })).toEqual([]);
  });
});

function sseChunk(eventType: string, data: object): string {
  return `event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`;
}

describe("TestPanel com base de conhecimento", () => {
  it("mostra as fontes consultadas abaixo da resposta", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(c) {
        for (const chunk of [
          sseChunk("RunStarted", { session_id: "s1", run_id: "r1" }),
          sseChunk("ToolCallCompleted", { tool: { tool_name: "buscar_rh", result: busca } }),
          sseChunk("RunContent", { content: "São trinta dias." }),
          sseChunk("RunCompleted", {}),
        ])
          c.enqueue(encoder.encode(chunk));
        c.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, body } as unknown as Response));

    render(<TestPanel agentId="a1" defaultOpen />);
    await userEvent.type(screen.getByPlaceholderText(/Digite uma mensagem/i), "férias?");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => expect(screen.getByText("São trinta dias.")).toBeInTheDocument());
    const fontes = screen.getByRole("list", { name: "Fontes" });
    expect(fontes).toHaveTextContent("ferias");
    expect(fontes).toHaveTextContent("reembolso");
    expect(fontes).toHaveTextContent("Políticas de RH");
  });
});
