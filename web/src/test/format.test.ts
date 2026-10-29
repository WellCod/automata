import { describe, expect, it } from "vitest";
import { formatDuration, formatTotalUsd } from "@/lib/format";

// o Intl separa o símbolo da moeda com espaço não separável
const plain = (s: string) => s.replace(/\s/g, " ");

describe("formatação do painel", () => {
  it("tempo em pt-BR, com vírgula e unidade separada", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(850)).toBe("850 ms");
    expect(formatDuration(4500)).toBe("4,5 s");
    expect(formatDuration(12_000)).toBe("12 s");
  });

  it("custo com duas casas a partir de 1 dólar e até quatro abaixo", () => {
    expect(plain(formatTotalUsd(46.6832))).toBe("US$ 46,68");
    expect(plain(formatTotalUsd(0.016))).toBe("US$ 0,016");
    expect(plain(formatTotalUsd(0))).toBe("US$ 0,00");
    expect(formatTotalUsd(null)).toBe("—");
  });
});
