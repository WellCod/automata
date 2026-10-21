"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

export type Connector = components["schemas"]["ConnectorResponse"];
export type ConnectorInput = components["schemas"]["ConnectorInput"];
export type ConnectorKind = ConnectorInput["kind"];
export type ConnectorTest = components["schemas"]["ConnectorTestResult"];

export const KIND_LABEL: Record<ConnectorKind, string> = {
  github: "GitHub",
  s3: "S3",
  sharepoint: "SharePoint",
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
};

export const SECRET_FIELDS: Record<ConnectorKind, FieldSpec[]> = {
  github: [{ key: "token", label: "Token (leitura; vazio para repositório público)" }],
  s3: [
    { key: "access_key_id", label: "Access key ID (vazio = credencial da máquina)" },
    { key: "secret_access_key", label: "Secret access key" },
  ],
  sharepoint: [{ key: "client_secret", label: "Client secret", required: true }],
};

export function origin(c: Pick<Connector, "kind" | "settings">): string {
  const s = c.settings as Record<string, string | null | undefined>;
  if (c.kind === "github") return `${s.repo}@${s.branch || "main"}${s.path ? `/${s.path}` : ""}`;
  if (c.kind === "s3") return `${s.bucket}${s.prefix ? `/${s.prefix}` : ""}`;
  return `${s.hostname}${s.site_path ?? ""}${s.folder_path ? `/${s.folder_path}` : ""}`;
}

export function summaryText(summary: Connector["last_summary"]): string {
  if (!summary) return "";
  const n = (k: string) => Number((summary as Record<string, unknown>)[k] ?? 0);
  const parts = [
    `${n("added")} novo(s)`,
    `${n("updated")} atualizado(s)`,
    `${n("removed")} removido(s)`,
    `${n("unchanged")} sem mudança`,
  ];
  if (n("failed")) parts.push(`${n("failed")} com falha`);
  if (n("skipped")) parts.push(`${n("skipped")} fora (tipo ou tamanho)`);
  return parts.join(" · ");
}

// Enquanto algum conector sincroniza, consulta de novo a cada 3 s
export function useConnectors(baseId: string) {
  return useQuery({
    queryKey: ["knowledge-bases", baseId, "connectors"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/knowledge-bases/{base_id}/connectors", {
        params: { path: { base_id: baseId } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao carregar conectores"));
      return res.data!;
    },
    refetchInterval: (query) =>
      query.state.data?.some((c) => c.last_status === "running") ? 3_000 : false,
  });
}
