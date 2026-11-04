import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DataSubjectsPanel, RequestsTable } from "@/components/data-subjects-panel";
import {
  customPatternProblems,
  DEFAULT_GUARDRAILS,
  type Guardrails,
  GuardrailsEditor,
} from "@/components/guardrails-editor";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn() },
}));

import client from "@/lib/api/client";

const ANA = "ana@cliente.com";

const exportDone = {
  id: "11111111-1111-1111-1111-111111111111",
  kind: "export",
  subject: ANA,
  subject_hash: "a".repeat(64),
  status: "done",
  requested_by: "owner@automata.dev",
  counts: { sessions: 1, memories: 2 },
  error: null,
  expires_at: "2026-11-11T12:00:00Z",
  created_at: "2026-11-04T12:00:00Z",
  finished_at: "2026-11-04T12:00:01Z",
};
const eraseDone = {
  ...exportDone,
  id: "22222222-2222-2222-2222-222222222222",
  kind: "erase",
  subject: null,
  subject_hash: "b".repeat(64),
  expires_at: null,
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("titulares", () => {
  it("consulta, mostra as contagens e só apaga com o id digitado", async () => {
    vi.mocked(client.GET).mockImplementation((async (path: string) =>
      path === "/api/v1/data-subject-requests"
        ? { data: [], error: undefined }
        : {
            data: { user_id: ANA, counts: { sessions: 2, memories: 1, traces: 0 }, total: 3 },
            error: undefined,
          }) as never);
    vi.mocked(client.POST).mockResolvedValue({ data: eraseDone, error: undefined } as never);
    const user = userEvent.setup();
    render(<DataSubjectsPanel />, { wrapper });

    await user.type(screen.getByLabelText("Id do titular"), ANA);
    await user.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByText("Conversas")).toBeInTheDocument();
    expect(screen.getByText("Memórias")).toBeInTheDocument();
    expect(screen.queryByText("Traces")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Apagar os dados" }));
    const apagar = screen.getByRole("button", { name: "Apagar definitivamente" });
    expect(apagar).toBeDisabled();
    const confirm = screen.getByLabelText(`Digite ${ANA} para confirmar`);
    await user.type(confirm, "ana");
    expect(apagar).toBeDisabled();
    await user.clear(confirm);
    await user.type(confirm, ANA);
    await user.click(apagar);
    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    const [path, opts] = vi.mocked(client.POST).mock.calls[0] as unknown as [
      string,
      { params: { path: { user_id: string } }; body: unknown },
    ];
    expect(path).toBe("/api/v1/data-subjects/{user_id}/erase");
    expect(opts.params.path.user_id).toBe(ANA);
    expect(opts.body).toEqual({ confirm: ANA });
  });

  it("titular sem nada guardado não mostra as ações", async () => {
    vi.mocked(client.GET).mockImplementation((async (path: string) =>
      path === "/api/v1/data-subject-requests"
        ? { data: [], error: undefined }
        : {
            data: { user_id: "x", counts: { sessions: 0 }, total: 0 },
            error: undefined,
          }) as never);
    const user = userEvent.setup();
    render(<DataSubjectsPanel />, { wrapper });
    await user.type(screen.getByLabelText("Id do titular"), "x");
    await user.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByText("Nada guardado para x.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Exportar os dados" })).not.toBeInTheDocument();
  });

  it("pedidos: download só na exportação pronta e exclusão só com o hash", () => {
    render(<RequestsTable requests={[exportDone, eraseDone] as never} />);
    const [, exportRow, eraseRow] = screen.getAllByRole("row");
    const link = within(exportRow!).getByRole("link", { name: "Baixar" });
    expect(link).toHaveAttribute(
      "href",
      `/api/api/v1/data-subject-requests/${exportDone.id}/download`,
    );
    expect(within(exportRow!).getByText(/3 linhas/)).toBeInTheDocument();
    expect(within(eraseRow!).getByText(`hash ${"b".repeat(12)}`)).toBeInTheDocument();
    expect(within(eraseRow!).queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("padrões próprios na máscara", () => {
  it("adiciona padrão e manda no payload", async () => {
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
    await user.click(screen.getByRole("button", { name: "Adicionar padrão" }));
    const group = screen.getByRole("group", { name: "Padrão 1" });
    await user.type(within(group).getByLabelText("Rótulo"), "matrícula");
    await user.type(within(group).getByLabelText("Prefixo"), "MAT");
    expect(last.pii?.custom).toEqual([
      { label: "matrícula", prefix: "MAT", min_digits: 6, max_digits: 10 },
    ]);
    await user.click(within(group).getByRole("button", { name: "Remover o padrão 1" }));
    expect(last.pii?.custom).toEqual([]);
  });

  it("aponta os mesmos problemas que a API recusa", () => {
    expect(
      customPatternProblems([{ label: "matrícula", prefix: "MAT", min_digits: 6, max_digits: 8 }]),
    ).toEqual([]);
    const problems = customPatternProblems([
      { label: "", prefix: "MAT(", min_digits: 9, max_digits: 8 },
      { label: "a", prefix: "", min_digits: 3, max_digits: 8 },
      { label: "A", prefix: "", min_digits: 6, max_digits: 8 },
    ]);
    expect(problems).toEqual([
      "Padrão 1: o rótulo precisa de 1 a 30 letras, dígitos ou espaços.",
      "Padrão 1: o prefixo aceita até 10 letras, dígitos ou hífen.",
      "Padrão 1: o mínimo de dígitos passa do máximo.",
      "Padrão 2: os dígitos vão de 4 a 20.",
      "Padrão 3: rótulo repetido.",
    ]);
  });
});
