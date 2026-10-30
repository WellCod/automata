// Números do painel em pt-BR, iguais em toda tela: vírgula decimal e unidade separada
const durationFmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${durationFmt.format(ms / 1000)} s`;
}

// Duas casas a partir de 1 dólar; abaixo disso até quatro, para o custo de um teste
// não virar "US$ 0,00"
export function formatTotalUsd(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: Math.abs(value) >= 1 ? 2 : 4,
  });
}
