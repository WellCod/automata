import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { InfoHint } from "@/components/ui/info-hint";
import { LATENCY_HINTS } from "@/lib/metric-hints";

describe("InfoHint", () => {
  it("mostra a explicação ao passar o mouse", async () => {
    const user = userEvent.setup();
    render(
      <InfoHint label="p95" ariaLabel="O que é p95">
        {LATENCY_HINTS.p95}
      </InfoHint>,
    );
    expect(screen.queryByText(LATENCY_HINTS.p95)).not.toBeInTheDocument();
    await user.hover(screen.getByRole("button", { name: "O que é p95" }));
    expect(await screen.findByText(LATENCY_HINTS.p95)).toBeInTheDocument();
  });

  it("abre pelo teclado", async () => {
    const user = userEvent.setup();
    render(
      <InfoHint label="p50" ariaLabel="O que é p50">
        {LATENCY_HINTS.p50}
      </InfoHint>,
    );
    await user.tab();
    expect(screen.getByRole("button", { name: "O que é p50" })).toHaveFocus();
    expect(await screen.findByText(LATENCY_HINTS.p50)).toBeInTheDocument();
  });
});
