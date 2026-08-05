import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TBody, TD, TH, THead, TR, Table } from "./Table";

function rows(onClick?: () => void) {
  render(
    <Table>
      <THead>
        <TR>
          <TH>کاربر</TH>
        </TR>
      </THead>
      <TBody>
        <TR onClick={onClick} label="گشودن کارت کاربر ۵۰۰">
          <TD>۵۰۰</TD>
        </TR>
      </TBody>
    </Table>,
  );
}

describe("an activatable table row", () => {
  // Users and SiteDevices both open their record dialog from a row click. Mouse-only, a
  // keyboard operator could not open a single record on either page.
  it("is reachable by keyboard and names the record it opens", async () => {
    const onClick = vi.fn();
    rows(onClick);
    await userEvent.tab();
    const row = screen.getByRole("button", { name: "گشودن کارت کاربر ۵۰۰" });
    expect(document.activeElement).toBe(row);
  });

  it("activates on Enter and on Space", async () => {
    const onClick = vi.fn();
    rows(onClick);
    screen.getByRole("button", { name: "گشودن کارت کاربر ۵۰۰" }).focus();
    await userEvent.keyboard("{Enter}");
    await userEvent.keyboard(" ");
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("stays a plain row when it does nothing", () => {
    rows(undefined);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("row", { name: /۵۰۰/ })).not.toHaveAttribute("tabindex");
  });

  it("scopes its header cells to their column", () => {
    rows();
    expect(screen.getByRole("columnheader", { name: "کاربر" })).toHaveAttribute("scope", "col");
  });
});
