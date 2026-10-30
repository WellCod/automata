import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/app-shell";

const nav = vi.hoisted(() => ({ pathname: "/" }));

vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(async () => ({ data: [], error: undefined })) },
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("menu no celular", () => {
  beforeEach(() => {
    nav.pathname = "/";
  });

  it("abre pelo botão e fecha com Esc, pelo botão de fechar e ao navegar", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<AppShell>conteúdo</AppShell>, { wrapper });
    const menu = screen.getByRole("complementary", { name: "Menu" });
    const open = screen.getByRole("button", { name: "Abrir menu" });
    expect(open).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveClass("-translate-x-full");

    await user.click(open);
    expect(open).toHaveAttribute("aria-expanded", "true");
    expect(menu).toHaveClass("translate-x-0");
    await user.keyboard("{Escape}");
    expect(menu).toHaveClass("-translate-x-full");

    await user.click(open);
    await user.click(screen.getByRole("button", { name: "Fechar menu" }));
    expect(menu).toHaveClass("-translate-x-full");

    await user.click(open);
    act(() => {
      nav.pathname = "/analytics";
    });
    rerender(<AppShell>outra página</AppShell>);
    expect(menu).toHaveClass("-translate-x-full");
  });

  it("login fica sem menu", () => {
    nav.pathname = "/login";
    render(<AppShell>entrar</AppShell>, { wrapper });
    expect(screen.queryByRole("button", { name: "Abrir menu" })).toBeNull();
  });
});
