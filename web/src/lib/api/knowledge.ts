"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

export type KnowledgeBase = components["schemas"]["KnowledgeBaseResponse"];
export type KnowledgeContent = components["schemas"]["KnowledgeContentResponse"];
export type EmbedderInfo = components["schemas"]["EmbedderInfo"];
export type SearchHit = components["schemas"]["SearchHit"];

export function useKnowledgeBases() {
  return useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/knowledge-bases");
      if (!res.data) throw new Error("Falha ao carregar bases");
      return res.data;
    },
  });
}

export function useKnowledgeBase(baseId: string) {
  return useQuery({
    queryKey: ["knowledge-bases", baseId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/knowledge-bases/{base_id}", {
        params: { path: { base_id: baseId } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao carregar a base"));
      return res.data!;
    },
  });
}

export function useEmbedders() {
  return useQuery({
    queryKey: ["knowledge-bases", "embedders"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/knowledge-bases/embedders");
      if (!res.data) throw new Error("Falha ao carregar embedders");
      return res.data;
    },
    staleTime: 5 * 60_000,
  });
}

// Enquanto houver documento em processamento, consulta de novo a cada 3 s
export function useKnowledgeContents(baseId: string) {
  return useQuery({
    queryKey: ["knowledge-bases", baseId, "contents"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/knowledge-bases/{base_id}/contents", {
        params: { path: { base_id: baseId } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao carregar documentos"));
      return res.data!;
    },
    refetchInterval: (query) =>
      query.state.data?.some((c) => c.status === "processing") ? 3_000 : false,
  });
}

export async function uploadFile(baseId: string, file: File): Promise<KnowledgeContent> {
  const form = new FormData();
  form.append("file", file);
  const res = await client.POST("/api/v1/knowledge-bases/{base_id}/contents/file", {
    params: { path: { base_id: baseId } },
    // o tipo gerado espera o objeto do schema; o corpo real é multipart
    body: form as unknown as never,
    bodySerializer: (body) => body as unknown as FormData,
  });
  if (res.error) throw new Error(apiErrorMessage(res.error, `Falha ao enviar ${file.name}`));
  return res.data!;
}
