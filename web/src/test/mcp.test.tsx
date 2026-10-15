import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { McpServerForm, slugify } from "@/components/mcp-server-form";
import { type McpBinding, type McpServer, McpToolsSelector } from "@/components/mcp-tools-selector";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

const crm: McpServer = {
  id: "s1",
  name: "CRM",
  slug: "crm",
  url: "https://crm.exemplo.com/mcp",
  timeout_seconds: 30,
  header_names: ["Authorization"],
  tools: [
    { name: "buscar_cliente", description: "Busca cliente", input_schema: {} },
    { name: "cancelar_assinatura", description: "Cancela", input_schema: {} },
  ],
  tools_discovered_at: "2026-10-15T12:00:00Z",
  updated_by: "owner",
  created_at: "2026-10-15T12:00:00Z",
  updated_at: "2026-10-15T12:00:00Z",
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function Harness({ onValue }: { onValue: (v: McpBinding[]) => void }) {
  const [value, setValue] = useState<McpBinding[]>([]);
  return (
    <McpToolsSelector
      value={value}
      onChange={(v) => {
        setValue(v);
        onValue(v);
      }}
    />
  );
}

describe("McpToolsSelector", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockResolvedValue({ data: [crm], error: undefined } as never);
  });

  it("liga o servidor com todas as tools e depois restringe", async () => {
    const onValue = vi.fn();
    const user = userEvent.setup();
    render(<Harness onValue={onValue} />, { wrapper });

    await user.click(await screen.findByLabelText("CRM"));
    expect(onValue).toHaveBeenLastCalledWith([
      { server_id: "s1", tools: null, require_confirmation: [] },
    ]);

    await user.click(screen.getByLabelText("Escolher"));
    await user.click(screen.getByLabelText("Liberar cancelar_assinatura"));
    expect(onValue).toHaveBeenLastCalledWith([
      { server_id: "s1", tools: ["buscar_cliente"], require_confirmation: [] },
    ]);
  });

  it("confirmação só para tool liberada e some ao desliberar", async () => {
    const onValue = vi.fn();
    const user = userEvent.setup();
    render(<Harness onValue={onValue} />, { wrapper });

    await user.click(await screen.findByLabelText("CRM"));
    await user.click(screen.getByLabelText("Escolher"));
    await user.click(screen.getByLabelText("Pedir confirmação antes de cancelar_assinatura"));
    expect(onValue).toHaveBeenLastCalledWith([
      {
        server_id: "s1",
        tools: ["buscar_cliente", "cancelar_assinatura"],
        require_confirmation: ["cancelar_assinatura"],
      },
    ]);

    await user.click(screen.getByLabelText("Liberar cancelar_assinatura"));
    expect(onValue).toHaveBeenLastCalledWith([
      { server_id: "s1", tools: ["buscar_cliente"], require_confirmation: [] },
    ]);
    expect(screen.getByLabelText("Pedir confirmação antes de cancelar_assinatura")).toBeDisabled();
  });

  it("orienta quando não há servidor cadastrado", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: [], error: undefined } as never);
    render(<McpToolsSelector value={[]} onChange={vi.fn()} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/nenhum servidor mcp cadastrado/i)).toBeInTheDocument();
    });
  });
});

describe("McpServerForm", () => {
  it("gera slug a partir do nome", () => {
    expect(slugify("CRM Vendas São Paulo")).toBe("crm_vendas_sao_paulo");
    expect(slugify("123 api")).toBe("mcp_123_api");
  });

  it("na edição não reenvia headers salvos sem pedido explícito", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<McpServerForm server={crm} pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />);

    expect(screen.getByText("Salvos: Authorization")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0].headers).toBeNull();
  });

  it("no cadastro envia os headers digitados", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<McpServerForm pending={false} onSubmit={onSubmit} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Nome"), "ERP");
    const url = screen.getByLabelText("URL (streamable HTTP)");
    await user.clear(url);
    await user.type(url, "https://erp.exemplo.com/mcp");
    await user.click(screen.getByRole("button", { name: "Adicionar header" }));
    await user.type(screen.getByLabelText("Nome do header 1"), "Authorization");
    await user.type(screen.getByLabelText("Valor do header 1"), "Bearer x");
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toEqual({
      name: "ERP",
      slug: "erp",
      url: "https://erp.exemplo.com/mcp",
      timeout_seconds: 30,
      headers: { Authorization: "Bearer x" },
    });
  });
});
