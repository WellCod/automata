import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_GUARDRAILS,
  floorSummary,
  type Guardrails,
  GuardrailsEditor,
  guardrailProblems,
  withDefaults,
} from "@/components/guardrails-editor";
import { InstanceGuardrailsPanel } from "@/components/instance-guardrails-panel";
import { blockLabel } from "@/lib/guardrail-labels";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), PUT: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const floor: Guardrails = withDefaults({
  pii: { mode: "mask", types: ["cpf"], custom: [] },
  prompt_injection: true,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.GET).mockImplementation((async (path: string) => {
    if (path === "/api/v1/instance-guardrails")
      return { data: { settings: null, updated_by: null, updated_at: null }, error: undefined };
    return { data: { "claude-haiku-4-5": {} }, error: undefined };
  }) as never);
});

describe("piso da instância", () => {
  it("resume o que o piso impõe", () => {
    expect(floorSummary(floor)).toEqual([
      "Mascarar dados pessoais (CPF)",
      "Bloquear injeção de prompt",
    ]);
    expect(floorSummary(null)).toEqual([]);
  });

  it("editor do agente mostra o piso herdado", () => {
    render(<GuardrailsEditor value={DEFAULT_GUARDRAILS} onChange={() => {}} floor={floor} />, {
      wrapper,
    });
    const note = screen.getByRole("note", { name: "Piso da instância" });
    expect(within(note).getByText("Mascarar dados pessoais (CPF)")).toBeInTheDocument();
  });

  it("salva o piso e mostra o texto de quando vale", async () => {
    vi.mocked(client.PUT).mockResolvedValue({
      data: { settings: floor, updated_by: "owner", updated_at: "2026-11-04T12:00:00Z" },
      error: undefined,
    } as never);
    const user = userEvent.setup();
    render(<InstanceGuardrailsPanel />, { wrapper });
    expect(await screen.findByText(/sem publicar os agentes de novo/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remover piso" })).not.toBeInTheDocument();
    await user.click(screen.getByLabelText(/injeção de prompt/));
    await user.click(screen.getByRole("button", { name: "Salvar piso" }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    const [path, opts] = vi.mocked(client.PUT).mock.calls[0] as unknown as [
      string,
      { body: { settings: Guardrails } },
    ];
    expect(path).toBe("/api/v1/instance-guardrails");
    expect(opts.body.settings.prompt_injection).toBe(true);
  });
});

describe("classificador da resposta", () => {
  it("liga com prompt_leak e aponta o que falta", async () => {
    let last: Guardrails = DEFAULT_GUARDRAILS;
    function Harness() {
      const [value, setValue] = useState<Guardrails>(DEFAULT_GUARDRAILS);
      return (
        <GuardrailsEditor
          value={value}
          onChange={(v) => {
            last = v;
            setValue(v);
          }}
        />
      );
    }
    const user = userEvent.setup();
    render(<Harness />, { wrapper });
    await user.click(screen.getByLabelText(/Julgar a resposta com um classificador/));
    expect(last.output?.classifier?.checks).toEqual(["prompt_leak"]);
    expect(guardrailProblems(last)).toContain("Escolha o modelo do classificador da resposta.");
    const checks = screen.getByRole("group", { name: "Checagens da resposta" });
    await user.click(within(checks).getByLabelText(/Assunto fora/));
    expect(guardrailProblems(last)).toContain(
      "Descreva o que o agente atende para a checagem de assunto da resposta.",
    );
    expect(screen.getByRole("option", { name: "Bloquear a resposta" })).toBeInTheDocument();
  });

  it("rótulo do bloqueio pelo classificador da resposta", () => {
    expect(blockLabel("output_classifier")).toBe("Classificador da resposta");
  });
});
