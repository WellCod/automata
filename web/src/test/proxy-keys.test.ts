// @vitest-environment node
import { exportSPKI, generateKeyPair, SignJWT } from "jose";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { verifyToken } from "@/proxy";

type Pair = Awaited<ReturnType<typeof generateKeyPair>>;

let oldPair: Pair;
let newPair: Pair;

async function sign(pair: Pair, expiresIn = "1h") {
  return new SignJWT({ scopes: [] })
    .setProtectedHeader({ alg: "RS256" })
    .setSubject("u1")
    .setAudience("automata")
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .sign(pair.privateKey);
}

beforeAll(async () => {
  oldPair = await generateKeyPair("RS256", { extractable: true });
  newPair = await generateKeyPair("RS256", { extractable: true });
});

afterEach(() => vi.unstubAllEnvs());

describe("verificação do cookie durante a rotação da chave", () => {
  it("sem a anterior, token da chave velha é recusado", async () => {
    vi.stubEnv("JWT_PUBLIC_KEY", await exportSPKI(newPair.publicKey));
    vi.stubEnv("JWT_PREVIOUS_PUBLIC_KEY", "");
    await expect(verifyToken(await sign(newPair))).resolves.toBeUndefined();
    await expect(verifyToken(await sign(oldPair))).rejects.toThrow();
  });

  it("com a anterior, aceita as duas e mantém o vencido como vencido", async () => {
    vi.stubEnv("JWT_PUBLIC_KEY", await exportSPKI(newPair.publicKey));
    vi.stubEnv("JWT_PREVIOUS_PUBLIC_KEY", await exportSPKI(oldPair.publicKey));
    await expect(verifyToken(await sign(oldPair))).resolves.toBeUndefined();
    await expect(verifyToken(await sign(newPair))).resolves.toBeUndefined();
    await expect(verifyToken(await sign(oldPair, "-1m"))).rejects.toMatchObject({
      code: "ERR_JWT_EXPIRED",
    });
  });
});
