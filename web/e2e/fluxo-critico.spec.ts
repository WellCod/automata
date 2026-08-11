import { expect, test, type Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const AGENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const DRAFT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

const mockAgentPage = {
  items: [
    {
      id: AGENT_ID,
      name: "Agente Teste",
      description: "Um agente de demonstração",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-06-01T00:00:00Z",
      current_version: null,
      draft_version: {
        id: DRAFT_ID,
        version_number: 1,
        label: null,
        status: "draft",
        author: "panel",
        created_at: "2025-06-01T00:00:00Z",
      },
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
};

const mockAgentDetail = {
  ...mockAgentPage.items[0],
  payload: {
    schema_version: 1,
    model_id: "claude-sonnet-4-6",
    instructions: {
      persona: "Sou um assistente prestativo",
      situation: "",
      tone: "",
      objective: "",
      guardrails: "",
    },
    tools: [],
    capabilities: { extended_thinking: false, structured_output: false, vision: false },
    metadata: {},
  },
};

const mockCapabilities = {
  "claude-sonnet-4-6": { extended_thinking: false, structured_output: true, vision: true },
  "claude-opus-4-7": { extended_thinking: true, structured_output: true, vision: true },
};

const mockVersionSummary = {
  id: DRAFT_ID,
  version_number: 1,
  label: null,
  status: "draft",
  author: "panel",
  created_at: "2025-06-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function mockAllApiRoutes(page: Page) {
  await page.route("**/api/v1/**", (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/models/capabilities")) {
      return route.fulfill({ json: mockCapabilities });
    }
    if (url.includes("/versions")) {
      return route.fulfill({ json: [] });
    }
    if (url.includes("/usage/rollup")) {
      return route.fulfill({ json: [] });
    }
    if (url.includes("/linter") && method === "POST") {
      return route.fulfill({ json: [] });
    }
    if (url.includes("/draft") && method === "PUT") {
      return route.fulfill({ status: 201, json: mockVersionSummary });
    }
    if (url.match(/\/configs\/[^/?]+$/) && method === "GET") {
      return route.fulfill({ json: mockAgentDetail });
    }
    if (url.includes("/configs") && method === "GET") {
      return route.fulfill({ json: mockAgentPage });
    }
    return route.continue();
  });
}

// ---------------------------------------------------------------------------
// Testes
// ---------------------------------------------------------------------------

test.describe("Lista de agentes", () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApiRoutes(page);
  });

  test("exibe agentes carregados da API", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Agente Teste")).toBeVisible();
    await expect(page.getByText("Um agente de demonstração")).toBeVisible();
  });

  test("exibe badge de rascunho quando há draft_version", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Rascunho", { exact: true })).toBeVisible();
  });

  test("exibe estado vazio quando não há agentes", async ({ page }) => {
    await page.route("**/api/v1/configs*", (route) => {
      if (!route.request().url().includes("/configs/")) {
        return route.fulfill({
          json: { items: [], total: 0, page: 1, page_size: 20 },
        });
      }
      return route.continue();
    });
    await page.goto("/");
    await expect(page.getByText(/nenhum agente/i)).toBeVisible();
  });
});

test.describe("Formulário de edição", () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApiRoutes(page);
  });

  test("navega para o formulário ao clicar no agente", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Abrir Agente Teste" }).click();
    await expect(page).toHaveURL(`/agents/${AGENT_ID}`);
    await expect(page.locator('input[name="name"]')).toHaveValue("Agente Teste");
  });

  test("popula campos com dados do agente", async ({ page }) => {
    await page.goto(`/agents/${AGENT_ID}`);
    await expect(page.locator('input[name="name"]')).toHaveValue("Agente Teste");
    await expect(page.locator('textarea[name="instructions.persona"]')).toHaveValue(
      "Sou um assistente prestativo",
    );
  });

  test("exibe erro de validação quando nome é apagado", async ({ page }) => {
    await page.goto(`/agents/${AGENT_ID}`);
    await page.locator('input[name="name"]').fill("");
    await page.getByRole("button", { name: /salvar rascunho/i }).click();
    await expect(page.getByText("Nome obrigatório")).toBeVisible();
  });

  test("salva rascunho com sucesso", async ({ page }) => {
    await page.goto(`/agents/${AGENT_ID}`);
    await page.locator('input[name="name"]').fill("Agente Renomeado");
    await page.getByRole("button", { name: /salvar rascunho/i }).click();
    await expect(page.getByText("Salvo")).toBeVisible();
  });

  test("envia o payload correto ao salvar", async ({ page }) => {
    let capturedBody: unknown = null;

    await page.route("**/api/v1/configs/**/draft", async (route) => {
      try {
        capturedBody = route.request().postDataJSON();
      } catch {}
      return route.fulfill({ status: 201, json: mockVersionSummary });
    });

    await page.goto(`/agents/${AGENT_ID}`);
    await page.getByRole("button", { name: /salvar rascunho/i }).click();
    await expect(page.getByText("Salvo")).toBeVisible();

    expect(capturedBody).toMatchObject({
      name: "Agente Teste",
      payload: { model_id: "claude-sonnet-4-6" },
    });
  });

  test("exibe erro quando API de salvar falha", async ({ page }) => {
    await page.route("**/api/v1/configs/**/draft", (route) => {
      return route.fulfill({ status: 500, json: { detail: "erro interno" } });
    });

    await page.goto(`/agents/${AGENT_ID}`);
    await page.getByRole("button", { name: /salvar rascunho/i }).click();
    await expect(page.getByText("Erro ao salvar")).toBeVisible();
  });
});
