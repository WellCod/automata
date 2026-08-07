#!/usr/bin/env node
/**
 * Gera src/lib/api/schema.d.ts a partir do schema OpenAPI da API Python.
 *
 * Uso: node scripts/gen-api.mjs  (ou pnpm gen:api)
 * Requer: venv da api já criado (uv sync em api/).
 */
import { execSync } from "node:child_process";
import { writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { platform } from "node:process";
import openapiTS, { astToString } from "openapi-typescript";

const dir = dirname(fileURLToPath(import.meta.url));
const apiDir = resolve(dir, "../../api");
const outFile = resolve(dir, "../src/lib/api/schema.d.ts");

// Usa o Python do venv da API; fallback para uv se o venv ainda não existir
const venvPython =
  platform === "win32"
    ? resolve(apiDir, ".venv/Scripts/python.exe")
    : resolve(apiDir, ".venv/bin/python");

const python = existsSync(venvPython) ? `"${venvPython}"` : "uv run python";

console.log("exportando schema da API...");
const schemaJson = execSync(`${python} scripts/export_openapi.py`, {
  cwd: apiDir,
  env: { ...process.env, PYTHONPATH: apiDir },
}).toString();

const schema = JSON.parse(schemaJson);

console.log("gerando tipos TypeScript...");
const ast = await openapiTS(schema);
const output = astToString(ast);

writeFileSync(outFile, output);
console.log(`✓ ${outFile}`);
