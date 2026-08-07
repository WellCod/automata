import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ModelSelector } from "@/components/model-selector";
import type { CapabilityFlags } from "@/components/model-selector";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

const mockModels = {
  "claude-opus-4-7": { extended_thinking: true, structured_output: true, vision: true },
  "claude-haiku-4-5-20251001": {
    extended_thinking: false,
    structured_output: true,
    vision: false,
  },
};

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>;
}

const EMPTY_CAPS: CapabilityFlags = {
  extended_thinking: false,
  structured_output: false,
  vision: false,
};

describe("ModelSelector", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockResolvedValue({ data: mockModels, error: undefined } as never);
  });

  it("renderiza opções de modelo após carregar", async () => {
    render(<ModelSelector value="" capabilities={EMPTY_CAPS} onChange={vi.fn()} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "claude-opus-4-7" })).toBeInTheDocument();
    });
    expect(screen.getByRole("option", { name: "claude-haiku-4-5-20251001" })).toBeInTheDocument();
  });

  it("exibe capabilities ao selecionar modelo", async () => {
    render(<ModelSelector value="claude-opus-4-7" capabilities={EMPTY_CAPS} onChange={vi.fn()} />, {
      wrapper,
    });
    await waitFor(() => {
      expect(screen.getByLabelText(/pensamento estendido/i)).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/saída estruturada/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/visão/i)).toBeInTheDocument();
  });

  it("desabilita capabilities não suportadas pelo modelo", async () => {
    render(
      <ModelSelector
        value="claude-haiku-4-5-20251001"
        capabilities={EMPTY_CAPS}
        onChange={vi.fn()}
      />,
      { wrapper },
    );
    await waitFor(() => {
      expect(screen.getByLabelText(/pensamento estendido/i)).toBeDisabled();
    });
    expect(screen.getByLabelText(/saída estruturada/i)).not.toBeDisabled();
    expect(screen.getByLabelText(/visão/i)).toBeDisabled();
  });

  it("reseta capabilities não suportadas ao trocar de modelo", async () => {
    const onChange = vi.fn();
    render(
      <ModelSelector
        value="claude-opus-4-7"
        capabilities={{ extended_thinking: true, structured_output: true, vision: true }}
        onChange={onChange}
      />,
      { wrapper },
    );

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "claude-haiku-4-5-20251001" })).toBeInTheDocument();
    });

    await userEvent.selectOptions(screen.getByRole("combobox"), "claude-haiku-4-5-20251001");

    expect(onChange).toHaveBeenCalledWith("claude-haiku-4-5-20251001", {
      extended_thinking: false,
      structured_output: true,
      vision: false,
    });
  });

  it("chama onChange ao ativar capability suportada", async () => {
    const onChange = vi.fn();
    render(
      <ModelSelector value="claude-opus-4-7" capabilities={EMPTY_CAPS} onChange={onChange} />,
      { wrapper },
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/pensamento estendido/i)).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText(/pensamento estendido/i));

    expect(onChange).toHaveBeenCalledWith("claude-opus-4-7", {
      extended_thinking: true,
      structured_output: false,
      vision: false,
    });
  });
});
