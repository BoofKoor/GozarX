import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { api } from "@/lib/api";

import { SiteDevices } from "./SiteDevices";

let mock: MockAdapter;

const DEVICE = {
  uuid: "dev-a",
  handle: "GZ-AAAA",
  status: "active_config",
  site_panel_username: "s-aaa_1",
  referral_count: 3,
  referred_by: null,
  streak_count: 4,
  last_claim_at: "2026-08-01T10:00:00Z",
  ip_bucket: "10.0.0",
  has_fingerprint: true,
  created_at: "2026-07-01T10:00:00Z",
};

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <ConfirmProvider>
          <SiteDevices />
        </ConfirmProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mock = new MockAdapter(api);
});
afterEach(() => mock.restore());

describe("SiteDevices", () => {
  it("lists devices with their handle and status", async () => {
    mock.onGet("/admin/site/devices/").reply(200, {
      items: [DEVICE],
      total: 1,
      page: 1,
      page_size: 25,
    });
    renderAt("/site/devices");
    expect(await screen.findByText("GZ-AAAA")).toBeInTheDocument();
    // Scoped to the table: the status filter above it offers the same label as an option.
    const row = screen.getByText("GZ-AAAA").closest("tr")!;
    expect(row).toHaveTextContent("دارای کانفیگ");
    expect(row).toHaveTextContent("10.0.0");
  });

  it("passes an ip_bucket deep-link through to the query and shows it as a filter", async () => {
    mock.onGet("/admin/site/devices/").reply((config) => {
      // This is the link the anti-abuse panel produces; if the param were dropped the page would
      // silently show every device instead of the ones behind that IP.
      expect(config.params.ip_bucket).toBe("10.0.0");
      return [200, { items: [DEVICE], total: 1, page: 1, page_size: 25 }];
    });
    renderAt("/site/devices?ip_bucket=10.0.0");
    expect(await screen.findByText(/فقط دستگاه‌های پشت IP/)).toBeInTheDocument();
  });

  it("shows an empty state rather than a bare table", async () => {
    mock.onGet("/admin/site/devices/").reply(200, {
      items: [],
      total: 0,
      page: 1,
      page_size: 25,
    });
    renderAt("/site/devices");
    expect(await screen.findByText("دستگاهی یافت نشد")).toBeInTheDocument();
  });
});
