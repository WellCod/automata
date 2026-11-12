"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Download, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import { type CaseImportReport, exportCasesUrl, importCases } from "@/lib/api/evals";
import { cn } from "@/lib/utils";

interface Props {
  configId: string;
  hasCases: boolean;
}

/** Exportar e importar a suíte por CSV (ADR-0043), com a prévia antes de gravar.
 * Devolve os botões, para o cabeçalho, e a prévia, para baixo dele. */
export function useEvalCsv({ configId, hasCases }: Props) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<CaseImportReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function reset() {
    setFile(null);
    setReport(null);
    setError("");
    if (input.current) input.current.value = "";
  }

  async function preview(picked: File) {
    reset();
    setFile(picked);
    setBusy(true);
    try {
      setReport(await importCases(configId, picked, true));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao ler a planilha");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!file) return;
    setBusy(true);
    try {
      const done = await importCases(configId, file, false);
      if (done.created > 0) {
        toast.success(`${done.created} casos importados`);
        void queryClient.invalidateQueries({ queryKey: ["eval-cases", configId] });
        reset();
      } else {
        setReport(done);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao importar");
    } finally {
      setBusy(false);
    }
  }

  const failing = report?.rows.filter((r) => r.errors.length > 0) ?? [];

  const actions = (
    <>
      {hasCases && (
        <a
          href={exportCasesUrl(configId)}
          download
          className={cn(buttonVariants({ size: "sm", variant: "muted" }))}
        >
          <Download aria-hidden />
          Exportar CSV
        </a>
      )}
      <Button size="sm" variant="muted" disabled={busy} onClick={() => input.current?.click()}>
        <Upload aria-hidden />
        Importar CSV
      </Button>
      <input
        ref={input}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        aria-label="Planilha de casos"
        onChange={(e) => {
          const picked = e.target.files?.[0];
          if (picked) void preview(picked);
        }}
      />
    </>
  );

  const panel = (report || error) && (
    <div
      role="dialog"
      aria-label="Importar casos"
      className="border-border bg-card flex flex-col gap-2 rounded border px-3 py-2"
    >
      <p className="text-foreground text-[13px] font-medium">{file?.name}</p>
      {error && <p className="text-destructive text-[12px]">{error}</p>}
      {report && failing.length === 0 && (
        <p className="text-muted-foreground text-[12px]">
          {report.rows.length} casos prontos para entrar na suíte.
        </p>
      )}
      {failing.length > 0 && (
        <>
          <p className="text-destructive text-[12px]">
            {failing.length} de {report!.rows.length} linhas com problema. Nada é gravado até todas
            passarem.
          </p>
          <ul className="flex flex-col gap-1 text-[12px]">
            {failing.map((r) => (
              <li key={r.line}>
                <span className="text-foreground font-medium">
                  Linha {r.line}
                  {r.name ? ` (${r.name})` : ""}:
                </span>{" "}
                <span className="text-muted-foreground">{r.errors.join("; ")}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="flex justify-end gap-2">
        <Button size="sm" onClick={reset}>
          Cancelar
        </Button>
        {report && failing.length === 0 && (
          <Button size="sm" variant="accent" disabled={busy} onClick={() => void confirm()}>
            {busy ? "Importando…" : `Importar ${report.rows.length} casos`}
          </Button>
        )}
      </div>
    </div>
  );

  return { actions, panel: panel || null };
}
