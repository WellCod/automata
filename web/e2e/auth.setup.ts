import { importPKCS8, SignJWT } from "jose";
import { test as setup } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const AUTH_FILE = path.join(__dirname, ".auth/session.json");

setup("autenticar", async ({ context }) => {
  const pem = process.env.JWT_PRIVATE_KEY;
  if (!pem) throw new Error("JWT_PRIVATE_KEY não definida no ambiente do Playwright");

  const key = await importPKCS8(pem, "RS256");
  const token = await new SignJWT({ sub: "e2e@test.local", scope: "owner" })
    .setProtectedHeader({ alg: "RS256" })
    .setAudience("automata")
    .setExpirationTime("1h")
    .sign(key);

  await context.addCookies([
    {
      name: "automata_token",
      value: token,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);

  await context.storageState({ path: AUTH_FILE });
});
