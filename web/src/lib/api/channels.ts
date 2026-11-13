"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

export type Channel = components["schemas"]["ChannelResponse"];
export type ChannelInput = components["schemas"]["ChannelInput"];
export type ChannelUpdate = components["schemas"]["ChannelUpdate"];
export type ConversationSummary = components["schemas"]["ConversationSummary"];
export type ConversationDetail = components["schemas"]["ConversationDetail"];
export type ConversationStatus = "bot" | "human" | "closed";

// campos da credencial de cada provedor, na ordem do formulário (ADR-0044)
export const CREDENTIAL_FIELDS: Record<string, { key: string; label: string }[]> = {
  whatsapp: [
    { key: "access_token", label: "Token de acesso" },
    { key: "phone_number_id", label: "ID do número" },
    { key: "app_secret", label: "Chave secreta do app" },
    { key: "verify_token", label: "Token de verificação do webhook" },
  ],
  slack: [
    { key: "bot_token", label: "Bot token (xoxb-…)" },
    { key: "signing_secret", label: "Signing secret" },
  ],
};

export const KIND_LABEL: Record<string, string> = { whatsapp: "WhatsApp", slack: "Slack" };

export function useChannels() {
  return useQuery({
    queryKey: ["channels"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/channels");
      if (res.error) throw new Error("Falha ao carregar os canais. Apenas owners têm acesso.");
      return res.data!;
    },
  });
}

export function useSaveChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (
      args: { id: null; body: ChannelInput } | { id: string; body: ChannelUpdate },
    ) => {
      const res =
        args.id === null
          ? await client.POST("/api/v1/channels", { body: args.body })
          : await client.PUT("/api/v1/channels/{channel_id}", {
              params: { path: { channel_id: args.id } },
              body: args.body,
            });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o canal"));
      return res.data!;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["channels"] }),
  });
}

export function useConversations(status: ConversationStatus) {
  return useQuery({
    queryKey: ["conversations", status],
    queryFn: async () => {
      const res = await client.GET("/api/v1/conversations", { params: { query: { status } } });
      if (res.error) throw new Error("Falha ao carregar as conversas");
      return res.data!;
    },
    refetchInterval: 5000,
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: ["conversation", id],
    enabled: id !== null,
    queryFn: async () => {
      const res = await client.GET("/api/v1/conversations/{conversation_id}", {
        params: { path: { conversation_id: id! } },
      });
      if (res.error) throw new Error("Falha ao carregar a conversa");
      return res.data!;
    },
    refetchInterval: 5000,
  });
}

type Action = "take" | "release" | "close";

export function useConversationAction(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: { action: Action } | { action: "reply"; text: string }) => {
      const params = { params: { path: { conversation_id: id } } };
      const res =
        args.action === "reply"
          ? await client.POST("/api/v1/conversations/{conversation_id}/reply", {
              ...params,
              body: { text: args.text },
            })
          : args.action === "take"
            ? await client.POST("/api/v1/conversations/{conversation_id}/take", params)
            : args.action === "release"
              ? await client.POST("/api/v1/conversations/{conversation_id}/release", params)
              : await client.POST("/api/v1/conversations/{conversation_id}/close", params);
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha na conversa"));
      return res.data!;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["conversation", id] });
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
