import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  type Conversation,
  ConversationEditor,
  DEFAULT_CONVERSATION,
  withConversationDefaults,
} from "@/components/conversation-editor";

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

describe("ConversationEditor", () => {
  it("liga a compactação e ajusta limite, turnos e instruções do resumo", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />);

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
    });
  });

  it("versão antiga sem a seção ganha o padrão desligado", () => {
    expect(withConversationDefaults(undefined)).toEqual(DEFAULT_CONVERSATION);
    expect(withConversationDefaults({ compaction: true }).compact_at_tokens).toBe(16_000);
  });
});
