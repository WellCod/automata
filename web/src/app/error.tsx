"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-start gap-3 px-6 py-6">
      <h1 className="text-foreground text-sm font-medium">Algo deu errado</h1>
      <p className="text-muted-foreground text-[13px]">
        A página falhou ao carregar.
        {error.digest && <span> Código: {error.digest}</span>}
      </p>
      <Button onClick={reset}>Tentar de novo</Button>
    </div>
  );
}
