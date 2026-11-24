export type DiffLine = { kind: "same" | "removed" | "added"; text: string };

// acima disso a tabela da LCS fica grande demais para o navegador; mostra só que mudou
const MAX_CELLS = 250_000;

/** Diff por linha (LCS): é o que basta para quem revisa um parágrafo ou uma lista. */
export function diffLines(before: string, after: string): DiffLine[] | null {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  if (beforeLines.length * afterLines.length > MAX_CELLS) return null;
  // lcs[i][j]: tamanho da maior subsequência comum entre as linhas a partir de i e de j
  const lcs: number[][] = Array.from({ length: beforeLines.length + 1 }, () =>
    new Array<number>(afterLines.length + 1).fill(0),
  );
  for (let i = beforeLines.length - 1; i >= 0; i--)
    for (let j = afterLines.length - 1; j >= 0; j--)
      lcs[i][j] =
        beforeLines[i] === afterLines[j]
          ? lcs[i + 1][j + 1] + 1
          : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  // percorre a tabela do começo: no empate, a remoção sai antes da inclusão
  const diff: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < beforeLines.length && j < afterLines.length) {
    if (beforeLines[i] === afterLines[j]) {
      diff.push({ kind: "same", text: beforeLines[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      diff.push({ kind: "removed", text: beforeLines[i++] });
    } else {
      diff.push({ kind: "added", text: afterLines[j++] });
    }
  }
  while (i < beforeLines.length) diff.push({ kind: "removed", text: beforeLines[i++] });
  while (j < afterLines.length) diff.push({ kind: "added", text: afterLines[j++] });
  return diff;
}
