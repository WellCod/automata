import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useEvalCsv } from "@/components/eval-csv";

vi.mock("@/lib/api/client", () => ({ default: { POST: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import client from "@/lib/api/client";

const ID = "cccccccc-cccc-cccc-cccc-cccccccccccc";

function Harness({ hasCases = true }: { hasCases?: boolean }) {
  const csv = useEvalCsv({ configId: ID, hasCases });
  return (
    <div>
      {csv.actions}
      {csv.panel}
    </div>
  );
}

function renderHarness(hasCases = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Harness hasCases={hasCases} />
    </QueryClientProvider>,
  );
}

const file = new File(["nome,mensagem\nA,oi\n"], "casos.csv", { type: "text/csv" });

beforeEach(() => vi.resetAllMocks());

describe("casos por CSV", () => {
  it("mostra a prévia e só grava depois de confirmar", async () => {
    vi.mocked(client.POST)
      .mockResolvedValueOnce({
        data: { created: 0, dry_run: true, rows: [{ line: 2, name: "A", errors: [] }] },
      } as never)
      .mockResolvedValueOnce({
        data: { created: 1, dry_run: false, rows: [{ line: 2, name: "A", errors: [] }] },
      } as never);
    renderHarness();

    await userEvent.upload(screen.getByLabelText("Planilha de casos"), file);
    expect(await screen.findByText("1 casos prontos para entrar na suíte.")).toBeInTheDocument();
    expect(vi.mocked(client.POST).mock.calls[0][1]).toMatchObject({
      params: { path: { config_id: ID }, query: { dry_run: true } },
    });

    await userEvent.click(screen.getByRole("button", { name: "Importar 1 casos" }));
    await waitFor(() =>
      expect(vi.mocked(client.POST).mock.calls[1][1]).toMatchObject({
        params: { query: { dry_run: false } },
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("lista as linhas com problema e não oferece importar", async () => {
    vi.mocked(client.POST).mockResolvedValueOnce({
      data: {
        created: 0,
        dry_run: true,
        rows: [
          { line: 2, name: "A", errors: [] },
          { line: 3, name: "B", errors: ["nome repetido no arquivo"] },
        ],
      },
    } as never);
    renderHarness();

    await userEvent.upload(screen.getByLabelText("Planilha de casos"), file);
    expect(await screen.findByText(/1 de 2 linhas com problema/)).toBeInTheDocument();
    expect(screen.getByText("Linha 3 (B):")).toBeInTheDocument();
    expect(screen.getByText("nome repetido no arquivo")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Importar \d/ })).not.toBeInTheDocument();
  });

  it("mostra o erro do arquivo inteiro", async () => {
    vi.mocked(client.POST).mockResolvedValueOnce({
      error: { detail: "Colunas desconhecidas: preco" },
    } as never);
    renderHarness();

    await userEvent.upload(screen.getByLabelText("Planilha de casos"), file);
    expect(await screen.findByText("Colunas desconhecidas: preco")).toBeInTheDocument();
  });

  it("exportar aponta para o BFF e some sem casos", () => {
    const { unmount } = renderHarness(true);
    expect(screen.getByRole("link", { name: "Exportar CSV" })).toHaveAttribute(
      "href",
      `/api/api/v1/configs/${ID}/eval-cases/export`,
    );
    unmount();
    renderHarness(false);
    expect(screen.queryByRole("link", { name: "Exportar CSV" })).not.toBeInTheDocument();
  });
});
