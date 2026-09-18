import { generateKeyPairSync } from "node:crypto";

import { defineConfig, devices } from "@playwright/test";

// Par RSA de teste, gerado uma vez por execução — nada de chave fixa no repositório.
// O Playwright reavalia este arquivo dentro dos workers, então o par precisa vir do
// ambiente quando já existe: gerar de novo faria o worker assinar o token com uma
// chave que o servidor, subido com a anterior, não reconhece.
function parDeTeste() {
  const privateKey = process.env.JWT_PRIVATE_KEY;
  const publicKey = process.env.JWT_PUBLIC_KEY;
  if (privateKey && publicKey) return { privateKey, publicKey };

  const par = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
    publicKeyEncoding: { type: "spki", format: "pem" },
  });
  // auth.setup.ts lê daqui; os workers herdam o ambiente do processo pai
  process.env.JWT_PRIVATE_KEY = par.privateKey;
  process.env.JWT_PUBLIC_KEY = par.publicKey;
  return par;
}

const { privateKey: E2E_PRIVATE_KEY, publicKey: E2E_PUBLIC_KEY } = parDeTeste();

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth/session.json",
      },
      dependencies: ["setup"],
    },
  ],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    env: {
      JWT_PRIVATE_KEY: E2E_PRIVATE_KEY,
      JWT_PUBLIC_KEY: E2E_PUBLIC_KEY,
      AUTOMATA_API_URL: "http://localhost:8000",
    },
  },
});
