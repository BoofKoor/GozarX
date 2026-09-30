import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

import { Settings } from "./Settings";
import { SiteSettings } from "./site/SiteSettings";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));

/**
 * A save made while the squad's location names are still loading.
 *
 * Resolved against a picker that had not arrived, every saved name read as stale and the save went
 * out as `[]` — "all of them" — so changing one number silently offered every location the operator
 * had unticked. Measured in a browser: both pages sent `locations: []` over a saved 6-of-7 subset.
 */

const BOT = {
  trial_squad: "sq-bot",
  locations: ["Germany", "Finland"],
  daily_limit_mb: 1024,
  referral_reward_mb: 100,
  referral_reward_limit: 10,
  trial_hours: 24,
  ads_enabled: false,
  configs_per_page: 8,
  ad_button_enabled: false,
  ad_button_text: "",
  ad_button_url: "",
  ad_button_emoji_id: "",
};

const SITE = {
  trial_squad: "sq-site",
  locations: ["Germany", "Finland"],
  popular_location: "Germany",
  trial_hours: 24,
  daily_limit_mb: 1024,
  referral_reward_mb: 100,
  referral_reward_limit: 10,
  reward_pwa_mb: 50,
  reward_push_mb: 50,
  reward_streak_mb: 50,
  streak_days: 3,
};

let mock: MockAdapter;

function renderPage(page: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{page}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Capture the body of the next PUT to `url`, answering with `reply`. */
function capturePut(url: string, reply: object) {
  const seen: { body?: Record<string, unknown> } = {};
  mock.onPut(url).reply((config) => {
    seen.body = JSON.parse(config.data as string);
    return [200, reply];
  });
  return seen;
}

beforeEach(() => {
  mock = new MockAdapter(api);
  mock.onGet("/admin/settings/").reply(200, BOT);
  mock.onGet("/admin/site/settings/").reply(200, SITE);
});
afterEach(() => mock.restore());

describe("saving before the squad's locations arrive", () => {
  it("the bot settings leave the saved list alone", async () => {
    mock.onGet("/admin/site/setup/locations").reply(() => new Promise(() => {})); // never answers
    const put = capturePut("/admin/settings/", BOT);
    renderPage(<Settings />);
    await userEvent.click(await screen.findByRole("button", { name: "ذخیره" }));
    await waitFor(() => expect(put.body).toBeDefined());
    expect(put.body).not.toHaveProperty("locations");
    expect(put.body).toMatchObject({ daily_limit_mb: 1024 });
  });

  it("the site settings leave the list and the star alone", async () => {
    mock.onGet("/admin/site/setup/locations").reply(() => new Promise(() => {}));
    const put = capturePut("/admin/site/settings/", SITE);
    renderPage(<SiteSettings />);
    await userEvent.click(await screen.findByRole("button", { name: "ذخیره" }));
    await waitFor(() => expect(put.body).toBeDefined());
    expect(put.body).not.toHaveProperty("locations");
    expect(put.body).not.toHaveProperty("popular_location");
  });

  it("still sends the ticked subset once the picker has loaded", async () => {
    mock.onGet("/admin/site/setup/locations").reply(200, ["Germany", "Finland", "Mexico"]);
    const put = capturePut("/admin/settings/", BOT);
    renderPage(<Settings />);
    await screen.findByText("Mexico"); // the picker is up
    await userEvent.click(screen.getByRole("button", { name: "ذخیره" }));
    await waitFor(() => expect(put.body).toBeDefined());
    expect(put.body?.locations).toEqual(["Germany", "Finland"]);
  });
});
