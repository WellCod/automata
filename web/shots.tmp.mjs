// Prints do README no ambiente automata-shots (web em 3002). Arquivo temporário, fora do git.
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const [loginFile, idsJson, outDir] = process.argv.slice(2);
const [email, password] = readFileSync(loginFile, "utf8").trim().split(/\s+/);
const ids = JSON.parse(idsJson);
const BASE = "http://localhost:3002";

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1.5,
  colorScheme: "dark",
});
await context.addInitScript(() => localStorage.setItem("automata-theme", "dark"));
const page = await context.newPage();

async function shot(name, target = page) {
  await page.waitForTimeout(600);
  await target.screenshot({ path: `${outDir}/${name}.png` });
  console.log("print:", name);
}

await page.goto(`${BASE}/login`);
await page.locator("#email").fill(email);
await page.locator("#password").fill(password);
await page.getByRole("button", { name: "Entrar" }).click();
await page.waitForURL(`${BASE}/`);
await page.waitForLoadState("networkidle");
await shot("agentes");

// workflow primeiro: a fila do replay começa nas respostas da triagem
await page.goto(`${BASE}/workflows/${ids.workflow}`);
await page.waitForLoadState("networkidle");
await shot("workflow");
await page.getByLabel("Mensagem para o workflow").fill("Fui cobrado duas vezes no pedido 4471, quero reembolso");
await page.getByRole("button", { name: "Rodar" }).click();
await page.getByRole("group", { name: "Revisão humana" }).waitFor({ timeout: 120_000 });
await shot("workflow-teste", page.locator("aside"));

// agente com o modo teste ao lado
await page.goto(`${BASE}/agents/${ids.atendimento}`);
await page.waitForLoadState("networkidle");
await page.getByLabel("Mensagem para o agente").fill("Como faço para redefinir minha senha?");
await page.keyboard.press("Enter");
await page.waitForTimeout(4000);
await shot("agente");
const guard = page.locator("fieldset").filter({ has: page.locator("legend", { hasText: /^Guardrails$/ }) });
await guard.scrollIntoViewIfNeeded();
await shot("guardrails", guard);

await page.getByRole("tab", { name: "Desempenho" }).click();
await page.getByRole("region", { name: "Orçamento do mês" }).waitFor();
await shot("orcamento");
await page.getByRole("tab", { name: "Testes" }).click();
await page.waitForLoadState("networkidle");
await shot("testes");

// memória no redator: a seção na configuração e a aba
await page.goto(`${BASE}/agents/${ids.redator}`);
await page.waitForLoadState("networkidle");
const memory = page.locator("fieldset").filter({ has: page.locator("legend", { hasText: "Memória do usuário" }) });
await memory.scrollIntoViewIfNeeded();
await shot("memoria-config", memory);
await page.getByRole("tab", { name: "Memória" }).click();
await page.waitForLoadState("networkidle");
await shot("memoria");

await page.goto(`${BASE}/times/${ids.time}`);
await page.waitForLoadState("networkidle");
await shot("time");

await page.goto(`${BASE}/aprovacoes`);
await page.waitForLoadState("networkidle");
await shot("aprovacoes");

await page.goto(`${BASE}/alertas`);
await page.waitForLoadState("networkidle");
await shot("alertas");

await page.goto(`${BASE}/conhecimento/${ids.base}`);
await page.waitForLoadState("networkidle");
await page.getByRole("tab", { name: "Conectores" }).click();
await page.waitForLoadState("networkidle");
await shot("conectores");
await page.getByRole("tab", { name: "Busca de teste" }).click();
await page.getByLabel("Pergunta").fill("Por que o run em background tem uma tentativa só?");
await page.getByRole("button", { name: "Buscar" }).click();
await page.waitForTimeout(3000);
await shot("conhecimento");

await page.goto(`${BASE}/analytics`);
await page.waitForLoadState("networkidle");
await page.waitForTimeout(1500);
await shot("analytics");

const light = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1.5,
  colorScheme: "light",
  storageState: await context.storageState(),
});
await light.addInitScript(() => localStorage.setItem("automata-theme", "light"));
const lightPage = await light.newPage();
await lightPage.goto(`${BASE}/analytics`);
await lightPage.waitForLoadState("networkidle");
await lightPage.waitForTimeout(1500);
await lightPage.screenshot({ path: `${outDir}/analytics-claro.png` });
console.log("print: analytics-claro");

await browser.close();
