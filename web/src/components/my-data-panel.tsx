"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { toast } from "sonner";
import { InventoryView, RequestsTable } from "@/components/data-subjects-panel";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { useMe } from "@/lib/api/users";

const KEY = ["me", "data"];
const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground focus:border-accent focus:outline-none";

/** Os dados do próprio usuário do painel (ADR-0036). */
export function MyDataPanel() {
  const id = useId();
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");

  const inventory = useQuery({
    queryKey: [...KEY, "inventory"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/me/data");
      if (res.error) throw new Error("Falha ao carregar os seus dados");
      return res.data;
    },
  });
  const requests = useQuery({
    queryKey: [...KEY, "requests"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/me/data/requests");
      if (res.error) throw new Error("Falha ao carregar os pedidos");
      return res.data;
    },
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.status === "pending" || r.status === "running")
        ? 2000
        : false,
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: KEY });
  const exportData = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/me/data/export");
      // a rota não declara erro no OpenAPI: só falha de rede ou de sessão chega aqui
      if (res.response.status >= 400) throw new Error("Falha ao pedir a cópia");
    },
    onSuccess: () => {
      toast.success("Cópia pedida. O arquivo aparece abaixo em instantes.");
      refresh();
    },
    onError: (e) => toast.error(e.message),
  });
  const erase = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/me/data/erase", { body: { confirm: typed } });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao pedir a exclusão"));
    },
    onSuccess: () => {
      toast.success("Exclusão pedida.");
      setConfirming(false);
      setTyped("");
      refresh();
    },
    onError: (e) => toast.error(e.message),
  });
  const email = me?.email ?? "";

  return (
    <div className="flex flex-col gap-4">
      <section className="border-border flex flex-col gap-3 rounded border px-4 py-3">
        {inventory.isLoading && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {inventory.error && (
          <p className="text-destructive text-[13px]">{inventory.error.message}</p>
        )}
        {inventory.data && <InventoryView inventory={{ ...inventory.data, user_id: "você" }} />}
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => exportData.mutate()} disabled={exportData.isPending}>
            Baixar uma cópia
          </Button>
          {!confirming && (
            <Button variant="subtleDestructive" onClick={() => setConfirming(true)}>
              Apagar meus dados
            </Button>
          )}
        </div>
        {confirming && (
          <div className="border-destructive/40 flex flex-col gap-2 rounded border px-4 py-3">
            <p className="text-foreground text-[13px]">
              Apaga o histórico das suas conversas, as memórias e as aprovações. No consumo, o seu
              id vira um pseudônimo. Não tem volta.
            </p>
            <label htmlFor={`${id}-confirm`} className="text-muted-foreground text-[12px]">
              Digite o seu e-mail ({email}) para confirmar
            </label>
            <input
              id={`${id}-confirm`}
              className={inputCls}
              value={typed}
              autoComplete="off"
              onChange={(e) => setTyped(e.target.value)}
            />
            <div className="flex gap-2">
              <Button
                variant="destructive"
                disabled={
                  !email || typed.trim().toLowerCase() !== email.toLowerCase() || erase.isPending
                }
                onClick={() => erase.mutate()}
              >
                Apagar definitivamente
              </Button>
              <Button
                variant="muted"
                onClick={() => {
                  setConfirming(false);
                  setTyped("");
                }}
              >
                Cancelar
              </Button>
            </div>
          </div>
        )}
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-foreground text-sm font-medium">Seus pedidos</h2>
        {requests.data && (
          <RequestsTable
            requests={requests.data}
            showRequester={false}
            downloadHref={(rid) => `/api/api/v1/me/data/requests/${rid}/download`}
          />
        )}
      </section>
    </div>
  );
}
