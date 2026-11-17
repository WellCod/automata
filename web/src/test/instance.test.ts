import { describe, expect, it } from "vitest";
import { formatUsd } from "@/lib/instance";

describe("custo em reais (UX-08)", () => {
  it("mostra o equivalente em reais só com cotação", () => {
    expect(formatUsd(1.5, null, 2).replace(/\s/g, " ")).toBe("US$ 1,50");
    expect(formatUsd(1.5, 5.4, 2).replace(/\s/g, " ")).toBe("US$ 1,50 (R$ 8,10)");
    expect(formatUsd(null, 5.4)).toBe("—");
  });
});
