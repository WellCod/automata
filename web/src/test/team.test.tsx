import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TeamMembersPicker, type TeamMemberValue } from "@/components/team-members-picker";
import { TestPanel } from "@/components/test-panel";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

const agents = [
  { id: "a1", name: "Consulta CRM", description: "Use para dados de cliente" },
  { id: "a2", name: "Cobrança", description: "Use para boletos" },
];

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function Harness({ onValue }: { onValue: (v: TeamMemberValue[]) => void }) {
  const [value, setValue] = useState<TeamMemberValue[]>([]);
  return (
    <TeamMembersPicker
      value={value}
      onChange={(v) => {
        setValue(v);
        onValue(v);
      }}
    />
  );
}

function sse(event: string, data: object): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function stream(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      chunks.forEach((x) => c.enqueue(enc.encode(x)));
      c.close();
    },
  });
}

describe("TeamMembersPicker", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      if ((path as string).endsWith("/versions")) {
        return {
          data: [
            { id: "v2", version_number: 2, status: "published" },
            { id: "v3", version_number: 3, status: "draft" },
          ],
          error: undefined,
        } as never;
      }
      return { data: { items: agents, total: 2 }, error: undefined } as never;
    });
  });

  it("adiciona membro seguindo a vigente e permite fixar versão publicada", async () => {
    const onValue = vi.fn();
    const user = userEvent.setup();
    render(<Harness onValue={onValue} />, { wrapper });

    await user.click(await screen.findByRole("checkbox", { name: /consulta crm/i }));
    expect(onValue).toHaveBeenLastCalledWith([{ agent_id: "a1", version_id: null }]);

    const select = await screen.findByLabelText("Versão de Consulta CRM");
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "Fixar v2" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("option", { name: "Fixar v3" })).not.toBeInTheDocument();
    await user.selectOptions(select, "v2");
    expect(onValue).toHaveBeenLastCalledWith([{ agent_id: "a1", version_id: "v2" }]);
  });
});

describe("TestPanel de time", () => {
  it("usa as rotas de time e mostra o rastro de delegação", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: stream([
        sse("TeamRunStarted", { session_id: "s1", run_id: "r1", team_id: "t1" }),
        sse("TeamToolCallStarted", {
          team_id: "t1",
          tool: {
            tool_name: "delegate_task_to_member",
            tool_args: { member_id: "a1", task: "busque o cliente 42" },
          },
        }),
        sse("ToolCallStarted", {
          agent_id: "a1",
          agent_name: "Consulta CRM",
          tool: { tool_name: "crm_buscar_cliente", tool_args: { cliente_id: "42" } },
        }),
        sse("RunContent", { agent_id: "a1", content: "texto do membro" }),
        sse("TeamRunContent", { team_id: "t1", content: "Cliente 42 é a Maria." }),
        sse("TeamRunCompleted", { team_id: "t1" }),
      ]),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(<TestPanel agentId="t1" kind="team" memberNames={{ a1: "Consulta CRM" }} defaultOpen />);
    await userEvent.type(screen.getByLabelText("Mensagem para o agente"), "quem é o 42?");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));

    await waitFor(() => expect(screen.getByText("Cliente 42 é a Maria.")).toBeInTheDocument());
    expect(fetchMock.mock.calls[0][0]).toBe("/api/teams/t1/runs");
    const rastro = screen.getByRole("list", { name: /rastro de delegação/i });
    expect(rastro).toHaveTextContent("Delegou a Consulta CRM: busque o cliente 42");
    expect(rastro).toHaveTextContent("Consulta CRM: Chamou crm_buscar_cliente");
    // a saída do membro não se mistura à resposta do time
    expect(screen.queryByText(/texto do membro/)).not.toBeInTheDocument();
  });
});
