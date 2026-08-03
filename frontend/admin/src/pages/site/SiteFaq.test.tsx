import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { toast } from "sonner";

import { api } from "@/lib/api";

import { SiteFaq } from "./SiteFaq";

// The page reports outcomes through sonner toasts, which need a <Toaster /> mounted to render.
// Spying on the call is the assertion that matters: what MESSAGE reached the operator.
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

let mock: MockAdapter;

const item = (id: number, question: string, extra: Record<string, unknown> = {}) => ({
  id,
  locale: "fa",
  category: "start",
  question,
  answer: `پاسخ ${id}`,
  position: id - 1,
  published: true,
  created_at: null,
  updated_at: null,
  ...extra,
});

const ITEMS = [item(1, "سوال یک"), item(2, "سوال دو"), item(3, "سوال سه", { published: false })];

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/site/faq"]}>
        <ConfirmProvider>
          <SiteFaq />
        </ConfirmProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mock = new MockAdapter(api);
  vi.mocked(toast.error).mockClear();
});
afterEach(() => mock.restore());

describe("SiteFaq", () => {
  it("lists the selected locale's questions and flags unpublished ones", async () => {
    mock.onGet("/admin/site/faq/").reply((config) => {
      expect(config.params.locale).toBe("fa");
      return [200, ITEMS];
    });
    renderPage();
    expect(await screen.findByText("سوال یک")).toBeInTheDocument();
    expect(screen.getByText("۱ مورد منتشرنشده")).toBeInTheDocument();
  });

  it("sends the whole new order in one reorder call", async () => {
    // Position edits one row at a time would need N requests and pass through a state where two
    // items claim the same slot; the server takes the full order or rejects it.
    mock.onGet("/admin/site/faq/").reply(200, ITEMS);
    let sent: number[] | null = null;
    mock.onPut("/admin/site/faq/reorder").reply((config) => {
      sent = JSON.parse(config.data).ids;
      return [200, ITEMS];
    });
    renderPage();
    await screen.findByText("سوال یک");

    await userEvent.click(screen.getAllByRole("button", { name: "انتقال به پایین" })[0]);
    await waitFor(() => expect(sent).toEqual([2, 1, 3]));
  });

  it("cannot reorder while a search is hiding rows", async () => {
    // The arrows move an item relative to its neighbours, and the neighbours on screen are not the
    // real ones when rows are filtered out.
    mock.onGet("/admin/site/faq/").reply(200, ITEMS);
    renderPage();
    await screen.findByText("سوال یک");

    await userEvent.type(screen.getByLabelText("جستجو در سوال‌ها"), "دو");
    await waitFor(() => expect(screen.queryByText("سوال یک")).not.toBeInTheDocument());
    for (const btn of screen.getAllByRole("button", { name: /انتقال به/ })) {
      expect(btn).toBeDisabled();
    }
  });

  it("surfaces the server's reason when a question is a duplicate", async () => {
    mock.onGet("/admin/site/faq/").reply(200, ITEMS);
    mock
      .onPost("/admin/site/faq/")
      .reply(409, { detail: "this question already exists in that language" });
    renderPage();
    await screen.findByText("سوال یک");

    await userEvent.click(screen.getByRole("button", { name: /سوال تازه/ }));
    await userEvent.type(screen.getByLabelText("سوال"), "سوال یک");
    await userEvent.type(screen.getByLabelText("پاسخ"), "پاسخ");
    await userEvent.click(screen.getByRole("button", { name: "ذخیره" }));

    // A 409 (duplicate) and a 422 (unknown category) must not collapse into one generic message.
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("this question already exists in that language"),
    );
  });

  it("explains that an empty list means the site falls back to its built-in questions", async () => {
    mock.onGet("/admin/site/faq/").reply(200, []);
    renderPage();
    expect(await screen.findByText("هنوز سوالی ثبت نشده")).toBeInTheDocument();
    expect(screen.getByText(/فهرست پیش‌فرض داخل کد/)).toBeInTheDocument();
  });
});
