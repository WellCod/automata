import { generateKeyPairSync } from "node:crypto";

import { defineConfig, devices } from "@playwright/test";

// Par RSA gerado a cada execução. Antes era fixo no arquivo — chave privada
// commitada é achado de scanner para sempre, mesmo sendo só de teste.
const { privateKey: E2E_PRIVATE_KEY, publicKey: E2E_PUBLIC_KEY } = generateKeyPairSync("rsa", {
  modulusLength: 2048,
  privateKeyEncoding: { type: "pkcs8", format: "pem" },
  publicKeyEncoding: { type: "spki", format: "pem" },
});

// Disponibiliza a chave privada para auth.setup.ts (roda no processo do Playwright)
process.env.JWT_PRIVATE_KEY = E2E_PRIVATE_KEY;

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
