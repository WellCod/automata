import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  type Conversation,
  ConversationEditor,
  DEFAULT_CONVERSATION,
  withConversationDefaults,
} from "@/components/conversation-editor";
import { MemoryEditor } from "@/components/memory-editor";

vi.mock("@/lib/api/client", () => ({ default: { GET: vi.fn() } }));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function Harness({ onChange }: { onChange: (v: Conversation) => void }) {
  const [value, setValue] = useState(DEFAULT_CONVERSATION);
  return (
    <ConversationEditor
      value={value}
      onChange={(v) => {
        setValue(v);
        onChange(v);
      }}
    />
  );
}

beforeEach(() => {
  vi.mocked(client.GET).mockResolvedValue({
    data: { "claude-haiku-4-5": {}, "claude-sonnet-4-6": {} },
    error: undefined,
  } as never);
});

describe("ConversationEditor", () => {
  it("liga a compactação e ajusta limite, turnos e instruções do resumo", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />, { wrapper });

    expect(screen.queryByLabelText("Limite em tokens")).toBeNull();
    await user.click(screen.getByRole("checkbox", { name: /resumir os turnos antigos/i }));
    expect(screen.getByText(/~21 páginas de texto/)).toBeInTheDocument();
    const limit = screen.getByLabelText("Limite em tokens");
    await user.clear(limit);
    await user.type(limit, "8000");
    await user.type(screen.getByLabelText("O que o resumo não pode perder"), "pedidos");

    expect(onChange.mock.calls.at(-1)![0]).toEqual({
      compaction: true,
      compact_at_tokens: 8000,
      keep_recent_runs: 3,
      summary_instructions: "pedidos",
      search_history: true,
      summary_model: null,
    });
  });

  it("escolhe um modelo próprio para o resumo", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />, { wrapper });
    await user.click(screen.getByRole("checkbox", { name: /resumir os turnos antigos/i }));
    const select = screen.getByLabelText("Modelo do resumo");
    await screen.findByRole("option", { name: "claude-haiku-4-5" });
    await user.selectOptions(select, "claude-haiku-4-5");
    expect(onChange.mock.calls.at(-1)![0].summary_model).toBe("claude-haiku-4-5");
    await user.selectOptions(select, "");
    expect(onChange.mock.calls.at(-1)![0].summary_model).toBeNull();
  });

  it("versão antiga sem a seção ganha o padrão desligado", () => {
    expect(withConversationDefaults(undefined)).toEqual(DEFAULT_CONVERSATION);
    expect(withConversationDefaults({ compaction: true }).compact_at_tokens).toBe(16_000);
  });
});

describe("MemoryEditor no time", () => {
  it("explica que a memória é do time e lida pelo líder", () => {
    render(
      <MemoryEditor
        value={{ enabled: true, instructions: null, retention_days: 90 }}
        onChange={() => {}}
        team
      />,
    );
    expect(screen.getByText(/o modelo do líder guarda/)).toBeInTheDocument();
    expect(screen.getByText(/Só este time lê/)).toBeInTheDocument();
  });
});
