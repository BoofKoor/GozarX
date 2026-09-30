import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError, type AxiosResponse } from "axios";
import { MemoryRouter } from "react-router-dom";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { useLogin } from "@/hooks/useAuth";

import { Login } from "./Login";

vi.mock("@/hooks/useAuth", () => ({ useLogin: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

/** Submit the form with `mutate` failing the way `error` does; return what was toasted. */
async function failWith(error: unknown): Promise<string> {
  cleanup();
  vi.mocked(toast.error).mockClear();
  vi.mocked(useLogin).mockReturnValue({
    mutate: (_vars: unknown, opts: { onError: (e: unknown) => void }) => opts.onError(error),
    isPending: false,
  } as unknown as ReturnType<typeof useLogin>);
  render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  );
  await userEvent.type(screen.getByLabelText("نام کاربری"), "admin");
  await userEvent.type(screen.getByLabelText("رمز عبور"), "pw");
  await userEvent.click(screen.getByRole("button", { name: "ورود" }));
  return String(vi.mocked(toast.error).mock.lastCall?.[0]);
}

const withStatus = (status: number) =>
  new AxiosError("x", "ERR", undefined, undefined, { status } as AxiosResponse);

describe("Login", () => {
  it("renders the login form", () => {
    vi.mocked(useLogin).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useLogin>);

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("نام کاربری")).toBeInTheDocument();
    expect(screen.getByLabelText("رمز عبور")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ورود" })).toBeInTheDocument();
  });

  it("tells a wrong password apart from a server that is down or unreachable", async () => {
    // Everything but a 503 read as "wrong password", so an operator with the right one retyped it
    // into the rate limit while the real problem was a restart or a dropped connection.
    expect(await failWith(withStatus(401))).toBe("نام کاربری یا رمز عبور نادرست است.");
    expect(await failWith(new AxiosError("Network Error", "ERR_NETWORK"))).toMatch(
      /به سرور دسترسی نیست/,
    );
    expect(await failWith(withStatus(502))).toMatch(/پاسخ نمی‌دهد/);
    expect(await failWith(withStatus(429))).toMatch(/تلاش‌های ورود زیاد بود/);
  });
});
