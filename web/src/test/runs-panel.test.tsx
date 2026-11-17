import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RunsPanel } from "@/components/runs-panel";

vi.mock("@/lib/api/client", () => ({ default: { GET: vi.fn() } }));
import client from "@/lib/api/client";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.resetAllMocks());

describe("Execuções (UX-07)", () => {
  it("filtra por status e pagina", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: { items: [], total: 0 } } as never);
    wrap(<RunsPanel agentId="a1" />);

    await userEvent.selectOptions(await screen.findByLabelText("Filtrar por status"), "error");
    await waitFor(() =>
      expect(client.GET).toHaveBeenLastCalledWith("/api/v1/configs/{config_id}/runs", {
        params: {
          path: { config_id: "a1" },
          query: { page: 1, page_size: 25, status: "error", since: undefined },
        },
      }),
    );
    expect(await screen.findByText("Nenhuma execução com esse filtro.")).toBeInTheDocument();
  });
});
