import { defineConfig, devices } from "@playwright/test";

// Chaves RSA exclusivas para testes — não usadas em produção
const E2E_PRIVATE_KEY = `-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDQhqsiXVslb7bG
3Gbc+YRoIYdvs7w/+Fam2EKFETyzlMsPqyk1P3wO5draPtOlN7UNJSbrac8ip75Q
zMtU6KS01b+wKbHq4xcPaaYs/fIxCn3nYuvjZXeGqSHI7kJ9Eo45oSLzTs2fKqiE
Jzc0ppct5a8Uq+VQQ9JXvjfvTj6icjOtBoG5bILIZLftH7WKw2NqDzmLYq6zdl3/
9ClkhKInLmVPvDq+x739x5eKIphraMTNsVEg2FEmhe6ijJlMRF/BeT5lnWIDM2FB
efHwtXYoUk3ggftV42tpSIV1OOzq1wkjlGtYSiEGy2WJxF42QcRfSHuNRiDsHEnq
mlfgtD0FAgMBAAECggEAMVTeqR1VWgys/Kw5IIdeGeVuvVAT1b1qQIPybrkWd3SY
un73W3vGnV6m8RFCcDh22mKC69gHEw+EkGh2pQJ5rrdPpz0h9GvfcXvAvq2gLZZq
FUK7g/sl9QNPtRGaxKyOXZdfpZhrwD8vCT6eypOrucW37wfAkwXMfgoIARLtce/t
mKlluqK8srTgZvGb05VhtAJEQRU7A8TIlIwOPI9UrXlYLMnWpNzooZGTA2zOH3IP
IljCrNrDvCrVkEK23SL21H5FKrdsacGvK9Jbq/0Ua6i12PQTynuIOhCJlkvnaQ4m
pPxTGrzFdqYhUfW5nhEWTJeWla44J8/EH849sB8aYQKBgQDxiJeCJ5/rL3TtvuiF
pyMPyopyJSwbAVt3SR8LlR3UltCbzCmf+xzkYV4O0JGAoHCZXxUteDWyhhfPKgZc
QYbGloX5kCc/1Uj7kvpZVC4E6mALfChs+W/uEufnGm1lNpzHlZjGb4npn63CFtBY
AsJq4cUMA6GauXsPFIATkOvMJQKBgQDdA/nbyt9B1TxeaHweWLcBNh4LIu/aHRQt
60zLzaqvv0ihFDfcre/vR1luBo8qF4GFJTFczr/HE7zgFdeia+j8urPnKNwtXO05
2wm5W0I5HGi639ucHUOfhejyv4ps8YnLFOVKRIlpPYFHOvHzY76/giWTosbNBhZA
s24zFYVnYQKBgF5szPZ4MT/LlMXhTZv6pG1m/Er1l1GTbUOsFXP8vuW+dB2Ean19
uWTbX98g0NFdZ8e98VSOW0fIvoQh5MyqXVtDu2q+XWnKIzce1bqYe0k2q4ex6Uf5
GDYVtA2YOk5IVHB+XnStZFguMcrgCmFt6r3IN7WjsckAXEif9hYwIM71AoGAWEg4
S8UzfJZycLuHqI+DOialxYkFCbjH0LfGiznxzhW4Ky9qSOnph0iWvk48bXHKOKbs
msey7xBBR7kx0x0LibgCGHnHyQ7va0bFEZcUUr+4Tb0RecBuvI++xwgfgPjSM557
IDlUMgdxVkSDVNco4FJaNCi3BDpENT/26szT5sECgYAhcNqglOBJJZiNBgpgaehC
fQDUmXUJOJDe6CyGKF25+157J6wSkSN2Xb6BTexxJZQuUpISsBnTyTqvyJLSdSSc
2RnUTrht7KnW8MqbeP90cVUxv86w0YkA7A9tNcRPdeAPjhQGaPr99UXTNS3zUfJM
dOF01ywOgN0VxRP6fCG1vw==
-----END PRIVATE KEY-----`;

const E2E_PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0IarIl1bJW+2xtxm3PmE
aCGHb7O8P/hWpthChRE8s5TLD6spNT98DuXa2j7TpTe1DSUm62nPIqe+UMzLVOik
tNW/sCmx6uMXD2mmLP3yMQp952Lr42V3hqkhyO5CfRKOOaEi807NnyqohCc3NKaX
LeWvFKvlUEPSV743704+onIzrQaBuWyCyGS37R+1isNjag85i2Kus3Zd//QpZISi
Jy5lT7w6vse9/ceXiiKYa2jEzbFRINhRJoXuooyZTERfwXk+ZZ1iAzNhQXnx8LV2
KFJN4IH7VeNraUiFdTjs6tcJI5RrWEohBstlicReNkHEX0h7jUYg7BxJ6ppX4LQ9
BQIDAQAB
-----END PUBLIC KEY-----`;

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
