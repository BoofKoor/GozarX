import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { NavTabs, Tabs } from "@/components/ui/Tabs";

import { ChromeProvider, SIDE_STACK, SidePanel } from "./chrome";

/**
 * jsdom has no layout, so these pin the DECLARATIONS whose absence produced two live bugs. The
 * proof that they are the right declarations came from measuring a real browser; what a test can
 * still do is stop a future edit from quietly dropping one.
 */
describe("side panel placement", () => {
  it("keeps children from shrinking, in whichever place the panel renders", () => {
    // No matchMedia match in jsdom, so this is the below-`xl` path: the inline host.
    render(
      <ChromeProvider>
        <SidePanel>
          <div data-testid="card">card</div>
        </SidePanel>
      </ChromeProvider>,
    );
    const host = screen.getByTestId("card").parentElement!;
    // A scrollable flex column whose children may shrink squeezes instead of scrolling, and the
    // whole shortfall lands on the child with no content floor — the radar SVG.
    expect(SIDE_STACK).toContain("[&>*]:shrink-0");
    for (const cls of SIDE_STACK.split(" ")) expect(host.className).toContain(cls);
    // And the panel's own width, so the inline copy cannot stretch a near-square chart across the
    // console: at 1100px wide it drew 968 across and 723 tall.
    expect(host.className).toContain("w-[19.5rem]");
  });
});

describe("tab strips", () => {
  const items = [
    { to: "/a", label: "A" },
    { to: "/b", label: "B" },
  ];

  it("never becomes a vertical scroll container", () => {
    // `overflow-x: auto` computes the other axis from `visible` to `auto`, so the axis we do not
    // want has to be named.
    const { container, rerender } = render(
      <MemoryRouter>
        <NavTabs items={items} />
      </MemoryRouter>,
    );
    expect(container.querySelector("div")!.className).toContain("overflow-y-hidden");

    rerender(
      <Tabs
        value="a"
        onChange={() => {}}
        items={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
        ]}
      />,
    );
    const strip = container.firstElementChild!;
    expect(strip.className).toContain("overflow-y-hidden");
    // The underline overlap belongs to the strip. On the tab it shortened the strip's content box
    // to 1px less than the tabs standing in it — a scrollbar, and a clipped 2px underline.
    expect(strip.className).toContain("-mb-px");
    for (const tab of strip.querySelectorAll("button"))
      expect(tab.className).not.toContain("-mb-px");
  });
});
