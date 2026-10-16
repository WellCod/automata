import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import UsersPage from "@/app/usuarios/page";
import { Sidebar } from "@/components/layout/sidebar";
import { temporaryPassword } from "@/lib/api/users";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

const user = (over: Record<string, unknown>) => ({
  id: "u1",
  email: "dono@empresa.com",
  role: "owner",
  is_active: true,
  created_at: "2026-10-16T12:00:00Z",
  last_login_at: "2026-10-16T13:00:00Z",
  ...over,
});

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function mockGet(role: string, users = [user({})]) {
  vi.mocked(client.GET).mockImplementation(async (path: string) => {
    if (path === "/api/v1/me") {
      return { data: { id: "u1", email: "dono@empresa.com", role }, error: undefined } as never;
    }
    if (path === "/api/v1/users") {
      return { data: users, error: undefined, response: { status: 200 } } as never;
    }
    return { data: [], error: undefined } as never;
  });
}

describe("UsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("cria usuário com senha temporária que atende a política", async () => {
    mockGet("owner");
    vi.mocked(client.POST).mockResolvedValue({
      data: user({ id: "u2", email: "nova@empresa.com", role: "editor" }),
      error: undefined,
    } as never);
    render(<UsersPage />, { wrapper });
    await userEvent.click(await screen.findByRole("button", { name: /novo usuário/i }));
    const form = screen.getByRole("form", { name: "Novo usuário" });
    await userEvent.type(within(form).getByLabelText("E-mail"), "nova@empresa.com");
    await userEvent.click(within(form).getByRole("button", { name: /criar usuário/i }));

    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    const [, opts] = vi.mocked(client.POST).mock.calls[0] as unknown as [
      string,
      { body: { email: string; role: string; password: string } },
    ];
    expect(opts.body.email).toBe("nova@empresa.com");
    expect(opts.body.role).toBe("editor");
    expect(opts.body.password).toMatch(/^(?=.*[A-Z])(?=.*\d).{12,}$/);
  });

  it("muda papel e só oferece remover para quem está desativado", async () => {
    mockGet("owner", [
      user({}),
      user({ id: "u2", email: "ativa@empresa.com", role: "editor" }),
      user({ id: "u3", email: "inativa@empresa.com", role: "viewer", is_active: false }),
    ]);
    vi.mocked(client.PATCH).mockResolvedValue({
      data: user({ id: "u2", email: "ativa@empresa.com", role: "viewer" }),
      error: undefined,
    } as never);
    render(<UsersPage />, { wrapper });

    const ativa = (await screen.findByText("ativa@empresa.com")).closest("tr")!;
    const inativa = screen.getByText("inativa@empresa.com").closest("tr")!;
    expect(within(ativa).queryByRole("button", { name: /^remover$/i })).not.toBeInTheDocument();
    expect(within(inativa).getByRole("button", { name: /^remover$/i })).toBeInTheDocument();
    expect(screen.getByText("(você)")).toBeInTheDocument();

    await userEvent.selectOptions(
      within(ativa).getByLabelText("Papel de ativa@empresa.com"),
      "viewer",
    );
    await waitFor(() =>
      expect(client.PATCH).toHaveBeenCalledWith("/api/v1/users/{user_id}", {
        params: { path: { user_id: "u2" } },
        body: { role: "viewer" },
      }),
    );
  });
});

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("mostra Usuários só para owner", async () => {
    mockGet("owner");
    const { unmount } = render(<Sidebar />, { wrapper });
    expect(await screen.findByRole("link", { name: /usuários/i })).toBeInTheDocument();
    unmount();

    mockGet("editor");
    render(<Sidebar />, { wrapper });
    await screen.findByText("dono@empresa.com");
    expect(screen.queryByRole("link", { name: /usuários/i })).not.toBeInTheDocument();
  });
});

describe("temporaryPassword", () => {
  it("gera senhas distintas dentro da política", () => {
    const a = temporaryPassword();
    expect(a).toMatch(/^(?=.*[A-Z])(?=.*\d).{12,}$/);
    expect(a).not.toBe(temporaryPassword());
  });
});
