import { importPKCS8, SignJWT } from "jose";

const ALG = "RS256";
const AUDIENCE = process.env.JWT_AUDIENCE ?? "automata";
const EXPIRY = "1h";

let _key: Awaited<ReturnType<typeof importPKCS8>> | null = null;

async function signingKey() {
  if (_key) return _key;
  const raw = process.env.JWT_PRIVATE_KEY;
  if (!raw) throw new Error("JWT_PRIVATE_KEY não definida");
  _key = await importPKCS8(raw, ALG);
  return _key;
}

export async function issueToken(userId: string, scopes: string[]): Promise<string> {
  const key = await signingKey();
  return new SignJWT({ sub: userId, scopes })
    .setProtectedHeader({ alg: ALG })
    .setIssuedAt()
    .setExpirationTime(EXPIRY)
    .setAudience(AUDIENCE)
    .sign(key);
}
