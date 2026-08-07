/**
 * Garante que env vars sensíveis não aparecem em código client-side.
 *
 * Varre todos os arquivos em src/ que podem ser importados pelo browser:
 * tudo exceto src/app/api/** (Route Handlers, executam no servidor).
 * Falha se qualquer arquivo exposto ao client referenciar as vars proibidas.
 *
 * Este teste não substitui uma auditoria de bundle real, mas captura
 * o caso mais comum: referência direta a process.env.CHAVE_SECRETA
 * em componente ou lib client-side.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(import.meta.dirname, "..");
const SERVER_ONLY_DIRS = [join(SRC_DIR, "app", "api"), join(SRC_DIR, "lib", "bff")];

const SENSITIVE_PATTERNS = [
  /process\.env\.JWT_PRIVATE_KEY/,
  /process\.env\.DATABASE_URL/,
  /process\.env\.ANTHROPIC_API_KEY/,
  /process\.env\.OPENAI_API_KEY/,
  // Qualquer var marcada NEXT_PUBLIC não deve ser usada para segredos:
  // este regex detecta tentativas de exfiltrar vars sensíveis via public prefix
  /NEXT_PUBLIC_JWT/,
  /NEXT_PUBLIC_.*KEY/i,
  /NEXT_PUBLIC_.*SECRET/i,
  /NEXT_PUBLIC_.*PASSWORD/i,
];

function collectFiles(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      collectFiles(full, files);
    } else if (
      /\.(ts|tsx)$/.test(entry) &&
      !entry.endsWith(".d.ts") &&
      !entry.endsWith(".test.ts") &&
      !entry.endsWith(".test.tsx")
    ) {
      files.push(full);
    }
  }
  return files;
}

function isServerOnly(filePath: string): boolean {
  return SERVER_ONLY_DIRS.some((d) => filePath.startsWith(d));
}

describe("bundle-secrets", () => {
  const clientFiles = collectFiles(SRC_DIR).filter((f) => !isServerOnly(f));

  it("nenhum arquivo client referencia env vars sensíveis", () => {
    const violations: string[] = [];

    for (const file of clientFiles) {
      const content = readFileSync(file, "utf-8");
      for (const pattern of SENSITIVE_PATTERNS) {
        if (pattern.test(content)) {
          violations.push(`${relative(SRC_DIR, file)}: ${pattern}`);
        }
      }
    }

    expect(
      violations,
      `Referências a segredos em código client:\n${violations.join("\n")}`,
    ).toEqual([]);
  });
});
