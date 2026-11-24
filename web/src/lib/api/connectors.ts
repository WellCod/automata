"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

export type Connector = components["schemas"]["ConnectorResponse"];
export type ConnectorInput = components["schemas"]["ConnectorInput"];
export type ConnectorKind = ConnectorInput["kind"];
export type ConnectorTest = components["schemas"]["ConnectorTestResult"];
export type ConnectorWebhook = components["schemas"]["ConnectorWebhook"];

export const KIND_LABEL: Record<ConnectorKind, string> = {
  github: "GitHub",
  s3: "S3",
  sharepoint: "SharePoint",
  gdrive: "Google Drive",
  gcs: "Cloud Storage",
};

interface FieldSpec {
  key: string;
  label: string;
  placeholder?: string;
  required?: boolean;
}

// mesmos campos de app/schemas/knowledge_connector.py; a API valida de novo
export const SETTINGS_FIELDS: Record<ConnectorKind, FieldSpec[]> = {
  github: [
    { key: "repo", label: "Repositório", placeholder: "empresa/documentacao", required: true },
    { key: "branch", label: "Branch", placeholder: "main" },
    { key: "path", label: "Pasta", placeholder: "docs/atendimento (vazio = repositório todo)" },
    { key: "api_url", label: "URL da API", placeholder: "https://api.github.com" },
  ],
  s3: [
    { key: "bucket", label: "Bucket", placeholder: "empresa-documentos", required: true },
    { key: "region", label: "Região", placeholder: "sa-east-1" },
    { key: "prefix", label: "Prefixo", placeholder: "contratos/ (vazio = bucket todo)" },
    { key: "endpoint_url", label: "Endpoint", placeholder: "vazio = AWS; preencha para MinIO" },
  ],
  sharepoint: [
    { key: "hostname", label: "Host", placeholder: "empresa.sharepoint.com", required: true },
    { key: "site_path", label: "Site", placeholder: "/sites/atendimento", required: true },
    { key: "folder_path", label: "Pasta", placeholder: "Procedimentos (vazio = biblioteca toda)" },
    { key: "tenant_id", label: "Tenant ID", required: true },
    { key: "client_id", label: "Client ID", required: true },
  ],
  gdrive: [
    {
      key: "folder_id",
      label: "ID da pasta",
      placeholder: "o trecho depois de /folders/ na URL",
      required: true,
    },
  ],
  gcs: [
    { key: "bucket", label: "Bucket", placeholder: "empresa-documentos", required: true },
    { key: "prefix", label: "Prefixo", placeholder: "contratos/ (vazio = bucket todo)" },
  ],
};

export const SECRET_FIELDS: Record<ConnectorKind, FieldSpec[]> = {
  github: [{ key: "token", label: "Token (leitura; vazio para repositório público)" }],
  s3: [
    { key: "access_key_id", label: "Access key ID (vazio = credencial da máquina)" },
    { key: "secret_access_key", label: "Secret access key" },
  ],
  sharepoint: [{ key: "client_secret", label: "Client secret", required: true }],
  gdrive: [{ key: "service_account_json", label: "JSON da conta de serviço", required: true }],
  gcs: [{ key: "service_account_json", label: "JSON da conta de serviço", required: true }],
};

// filtro por nome (ADR-0039): uma linha por padrão no formulário
export function patternsOf(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

export function parsePatterns(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

// resumo do filtro por nome para a lista de conectores
export function filterText(connector: Pick<Connector, "settings">): string {
  const settings = connector.settings as Record<string, unknown>;
  const include = patternsOf(settings.include);
  const exclude = patternsOf(settings.exclude);
  const parts: string[] = [];
  if (include.length) parts.push(`só ${include.join(", ")}`);
  if (exclude.length) parts.push(`fora ${exclude.join(", ")}`);
  return parts.join(" · ");
}

// de onde o conector lê, numa linha: repositório, bucket, pasta do Drive ou site do SharePoint
export function origin(connector: Pick<Connector, "kind" | "settings">): string {
  const settings = connector.settings as Record<string, string | null | undefined>;
  if (connector.kind === "github")
    return `${settings.repo}@${settings.branch || "main"}${settings.path ? `/${settings.path}` : ""}`;
  if (connector.kind === "s3" || connector.kind === "gcs")
    return `${settings.bucket}${settings.prefix ? `/${settings.prefix}` : ""}`;
  if (connector.kind === "gdrive") return `pasta ${settings.folder_id}`;
  return `${settings.hostname}${settings.site_path ?? ""}${settings.folder_path ? `/${settings.folder_path}` : ""}`;
}

// contagens da última sincronização; falha e arquivo pulado só aparecem quando houve
export function summaryText(summary: Connector["last_summary"]): string {
  if (!summary) return "";
  const count = (key: string) => Number((summary as Record<string, unknown>)[key] ?? 0);
  const parts = [
    `${count("added")} novo(s)`,
    `${count("updated")} atualizado(s)`,
    `${count("removed")} removido(s)`,
    `${count("unchanged")} sem mudança`,
  ];
  if (count("failed")) parts.push(`${count("failed")} com falha`);
  if (count("skipped")) parts.push(`${count("skipped")} fora (tipo ou tamanho)`);
  return parts.join(" · ");
}

// Enquanto algum conector sincroniza, consulta de novo a cada 3 s
export function useConnectors(baseId: string) {
  return useQuery({
    queryKey: ["knowledge-bases", baseId, "connectors"],
    queryFn: async () => {
      const result = await client.GET("/api/v1/knowledge-bases/{base_id}/connectors", {
        params: { path: { base_id: baseId } },
      });
      if (result.error)
        throw new Error(apiErrorMessage(result.error, "Falha ao carregar conectores"));
      return result.data!;
    },
    refetchInterval: (query) =>
      query.state.data?.some((connector) => connector.last_status === "running") ? 3_000 : false,
  });
}
