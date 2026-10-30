import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  EXAMPLE_SCHEMA,
  type OutputSchema,
  OutputSchemaEditor,
  parseSchema,
} from "@/components/output-schema-editor";
import {
  DEFAULT_RUN,
  missingCapabilities,
  type RunControls,
  RunControlsEditor,
} from "@/components/run-controls-editor";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

const MODELS = {
  "claude-sonnet-4-6": { extended_thinking: true, structured_output: true, vision: true },
  "gpt-4o": { extended_thinking: false, structured_output: true, vision: true },
  o3: { extended_thinking: false, structured_output: true, vision: false },
};
const VISION = { extended_thinking: false, structured_output: false, vision: true };

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.GET).mockResolvedValue({ data: MODELS, error: undefined } as never);
});

describe("controle do run", () => {
  it("reserva precisa das capabilities que o agente liga", () => {
    expect(missingCapabilities(MODELS.o3, VISION)).toEqual(["visão"]);
    expect(missingCapabilities(MODELS["gpt-4o"], VISION)).toEqual([]);
  });

  it("liga o limite, o retry e as reservas sem oferecer modelo incompatível", async () => {
    const seen: RunControls[] = [];
    function Harness() {
      const [value, setValue] = useState<RunControls>(DEFAULT_RUN);
      return (
        <RunControlsEditor
          value={value}
          onChange={(v) => {
            seen.push(v);
            setValue(v);
          }}
          modelId="claude-sonnet-4-6"
          capabilities={VISION}
        />
      );
    }
    const user = userEvent.setup();
    render(<Harness />, { wrapper });

    await user.click(screen.getByLabelText("Limitar chamadas de tool por run"));
    const limit = screen.getByLabelText("Máximo de chamadas de tool");
    await user.clear(limit);
    await user.type(limit, "4");
    await user.selectOptions(screen.getByLabelText("Tentativas extras no provedor"), "2");

    const first = screen.getByLabelText("Modelo reserva 1");
    await screen.findByRole("option", { name: "gpt-4o" });
    // o principal não aparece; o3 aparece desabilitado por falta de visão
    expect(within(first).queryByRole("option", { name: "claude-sonnet-4-6" })).toBeNull();
    expect(within(first).getByRole("option", { name: "o3 (sem visão)" })).toBeDisabled();
    await user.selectOptions(first, "gpt-4o");

    expect(seen.at(-1)).toEqual({
      tool_call_limit: 4,
      provider_retries: 2,
      fallback_models: ["gpt-4o"],
    });
    // a segunda reserva só aparece depois da primeira, sem repetir a escolhida
    const second = screen.getByLabelText("Modelo reserva 2");
    expect(within(second).getByRole("option", { name: "gpt-4o" })).toBeDisabled();
  });
});

describe("saída estruturada", () => {
  it("confere o básico do schema na hora", () => {
    expect(parseSchema("{").error).toBe("JSON inválido");
    expect(parseSchema("[]").error).toBe("O schema precisa ser um objeto JSON");
    expect(parseSchema('{"type": "array"}').error).toBe('A raiz precisa ter "type": "object"');
    expect(parseSchema(JSON.stringify(EXAMPLE_SCHEMA)).schema).toEqual(EXAMPLE_SCHEMA);
  });

  it("liga com o exemplo, edita e desliga", async () => {
    const seen: (OutputSchema | null)[] = [];
    function Harness() {
      const [value, setValue] = useState<OutputSchema | null>(null);
      return (
        <OutputSchemaEditor
          value={value}
          modelId="gpt-4o"
          onChange={(v) => {
            seen.push(v);
            setValue(v);
          }}
        />
      );
    }
    const user = userEvent.setup();
    render(<Harness />, { wrapper });
    const toggle = screen.getByLabelText(/Responder em JSON/);
    await vi.waitFor(() => expect(toggle).toBeEnabled());
    await user.click(toggle);
    expect(seen.at(-1)).toEqual(EXAMPLE_SCHEMA);

    const editor = screen.getByLabelText("JSON Schema");
    await user.clear(editor);
    await user.type(editor, '{{"type": "array"}');
    await user.tab();
    expect(screen.getByRole("alert")).toHaveTextContent('A raiz precisa ter "type": "object"');
    expect(seen.at(-1)).toEqual(EXAMPLE_SCHEMA);

    await user.click(toggle);
    expect(seen.at(-1)).toBeNull();
  });

  it("modelo sem saída estruturada não liga", async () => {
    render(<OutputSchemaEditor value={null} modelId="modelo-sem" onChange={() => {}} />, {
      wrapper,
    });
    expect(await screen.findByText("(modelo sem suporte)")).toBeInTheDocument();
    expect(screen.getByLabelText(/Responder em JSON/)).toBeDisabled();
  });
});
