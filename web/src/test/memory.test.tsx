import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MyMemoriesPage from "@/app/minhas-memorias/page";
import { groupByUser, MemoriesPanel, type MemoryItem } from "@/components/memories-panel";
import { DEFAULT_MEMORY, type Memory, MemoryEditor } from "@/components/memory-editor";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const item = (memory: string, user: string, agent = "a1"): MemoryItem => ({
  memory_id: `${user}-${memory}`,
  user_id: user,
  agent_id: agent,
  agent_name: "Loja",
  memory,
  topics: [],
  updated_at: "2026-10-21T10:00:00Z",
});

describe("memória do usuário", () => {
  beforeEach(() => vi.clearAllMocks());

  it("liga a memória com o que lembrar e a retenção", async () => {
    const seen: Memory[] = [];
    function Harness() {
      const [value, setValue] = useState<Memory>(DEFAULT_MEMORY);
      return (
        <MemoryEditor
          value={value}
          onChange={(v) => {
            seen.push(v);
            setValue(v);
          }}
        />
      );
    }
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.queryByLabelText("O que lembrar")).toBeNull();
    await user.click(screen.getByLabelText("Lembrar do usuário entre conversas"));
    await user.type(screen.getByLabelText("O que lembrar"), "tamanho");
    await user.selectOptions(screen.getByRole("combobox"), "30");
    expect(seen.at(-1)).toEqual({ enabled: true, instructions: "tamanho", retention_days: 30 });
  });

  it("agrupa por usuário", () => {
    const groups = groupByUser([item("b", "zeca"), item("a", "ana"), item("c", "ana")]);
    expect(groups.map(([u, list]) => [u, list.length])).toEqual([
      ["ana", 2],
      ["zeca", 1],
    ]);
  });

  it("owner esquece um usuário no agente", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: [item("Veste M", "ana"), item("Mora em Curitiba", "bruno")],
      error: undefined,
    } as never);
    vi.mocked(client.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<MemoriesPanel agentId="a1" />, { wrapper });
    const ana = await screen.findByRole("region", { name: "Memórias de ana" });
    await user.click(within(ana).getByRole("button", { name: "Esquecer usuário" }));
    await waitFor(() => expect(client.DELETE).toHaveBeenCalled());
    expect(vi.mocked(client.DELETE).mock.calls[0]).toEqual([
      "/api/v1/configs/{config_id}/memories",
      { params: { path: { config_id: "a1" }, query: { user_id: "ana" } } },
    ]);
  });

  it("usuário vê as próprias com o nome do agente e apaga uma", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: [item("Veste M", "me")],
      error: undefined,
    } as never);
    vi.mocked(client.DELETE).mockResolvedValue({ data: undefined, error: undefined } as never);
    const user = userEvent.setup();
    render(<MyMemoriesPage />, { wrapper });
    const list = await screen.findByRole("list", { name: "Memórias" });
    expect(list).toHaveTextContent("Veste M");
    expect(list).toHaveTextContent("Loja");
    await user.click(within(list).getByRole("button", { name: "Apagar" }));
    await waitFor(() => expect(client.DELETE).toHaveBeenCalled());
    expect(vi.mocked(client.DELETE).mock.calls[0]).toEqual([
      "/api/v1/me/memories/{memory_id}",
      { params: { path: { memory_id: "me-Veste M" } } },
    ]);
  });
});
