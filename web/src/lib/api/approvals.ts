import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";

export function usePendingApprovals() {
  return useQuery({
    queryKey: ["approvals"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/approvals");
      if (res.error) throw new Error("Falha ao carregar aprovações");
      return res.data!;
    },
    refetchInterval: 10_000,
  });
}
