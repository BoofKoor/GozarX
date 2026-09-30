import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { api } from "@/lib/api";

import { Texts } from "./Texts";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

let mock: MockAdapter;

const text = (key: string, fa: string) => ({
  key,
  fa,
  en: "",
  ru: "",
  placeholders: [],
  link_preview: true,
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ConfirmProvider>
        <Texts />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mock = new MockAdapter(api);
  mock.onGet("/admin/texts/").reply(200, [text("welcome", "سلام"), text("main_menu", "منو")]);
  mock.onPost("/admin/texts/preview").reply(200, { rendered: "", missing_placeholders: [] });
});
afterEach(() => mock.restore());

describe("Texts", () => {
  it("asks before another key's click throws away unsaved text", async () => {
    renderPage();
    await userEvent.click(await screen.findByText("welcome"));
    const fa = screen.getAllByRole("textbox")[1]; // [0] is the key search box
    await userEvent.type(fa, " دوباره");
    await userEvent.click(screen.getByText("main_menu"));
    // The confirm is up, and choosing to keep editing leaves the typed text where it was.
    await userEvent.click(await screen.findByRole("button", { name: "ادامهٔ ویرایش" }));
    expect(screen.getAllByRole("textbox")[1]).toHaveValue("سلام دوباره");
  });

  it("stops reading «unsaved» once a save the server cleaned has landed", async () => {
    // The server strips bidi marks out of {token}; compared with the TYPED text, a successful save
    // stayed «ذخیره‌نشده» for good.
    mock.onPut("/admin/texts/welcome").reply(200, text("welcome", "سلام {name}"));
    renderPage();
    await userEvent.click(await screen.findByText("welcome"));
    const fa = screen.getAllByRole("textbox")[1];
    await userEvent.clear(fa);
    await userEvent.type(fa, "سلام {{name‏}");
    expect(screen.getByText("ذخیره‌نشده")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "ذخیره" }));
    await waitFor(() => expect(screen.queryByText("ذخیره‌نشده")).not.toBeInTheDocument());
    expect(screen.getAllByRole("textbox")[1]).toHaveValue("سلام {name}");
  });
});
