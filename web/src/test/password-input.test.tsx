import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { PasswordInput } from "@/components/ui/password-input";

describe("PasswordInput", () => {
  it("começa oculto e alterna entre mostrar e ocultar", async () => {
    const user = userEvent.setup();
    render(<PasswordInput aria-label="Nova senha" defaultValue="Segredo12345" />);
    const input = screen.getByLabelText("Nova senha");
    expect(input).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(input).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Ocultar senha" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Ocultar senha" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("botão não envia o formulário", async () => {
    const user = userEvent.setup();
    let enviado = false;
    render(
      <form
        onSubmit={(e) => {
          e.preventDefault();
          enviado = true;
        }}
      >
        <PasswordInput aria-label="Senha" />
      </form>,
    );
    await user.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(enviado).toBe(false);
  });
});
