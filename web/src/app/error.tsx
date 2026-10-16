"use client";

import { useEffect } from "react";

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
      <button
        type="button"
        onClick={reset}
        className="border-border text-foreground hover:border-accent hover:text-accent inline-flex h-7 items-center rounded border px-3 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors"
      >
        Tentar de novo
      </button>
    </div>
  );
}
