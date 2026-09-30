import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { useFocusTrap } from "./useFocusTrap";

const noop = () => undefined;

function Dialog({ label, onClose }: { label: string; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, onClose);
  return (
    <div ref={ref} role="dialog" aria-label={label}>
      <button type="button">{`${label} first`}</button>
      <button type="button">{`${label} second`}</button>
    </div>
  );
}

function Palette() {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, noop);
  return (
    <div ref={ref} role="dialog" aria-label="palette">
      <input aria-label="search" />
      {/* Options out of the tab order, as the command palette renders them. */}
      <button type="button" tabIndex={-1}>
        option one
      </button>
      <button type="button" tabIndex={-1}>
        option last
      </button>
    </div>
  );
}

describe("useFocusTrap", () => {
  it("wraps on the TABBABLE elements, not on controls taken out of the tab order", async () => {
    // The selector matched every button, so an untabbable option was the trap's last element:
    // Shift+Tab from the input landed on it (Enter then ran it), and Tab walked out of the dialog.
    render(<Palette />);
    const input = screen.getByLabelText("search");
    expect(document.activeElement).toBe(input);
    await userEvent.keyboard("{Shift>}{Tab}{/Shift}");
    expect(document.activeElement).toBe(input);
    await userEvent.tab();
    expect(document.activeElement).toBe(input);
  });

  it("keeps focus where it is when the parent re-renders with a new onClose", async () => {
    // Callers pass an inline `() => setX(null)`: a new function every render. As an effect
    // dependency it rebuilt the trap on each render and dropped focus back on the first button.
    let bump = () => {};
    function Parent() {
      const [n, setN] = useState(0);
      bump = () => setN(n + 1);
      return <Dialog label={`d`} onClose={() => void n} />;
    }
    render(<Parent />);
    screen.getByText("d second").focus();
    // A re-render driven from outside the dialog (a refetch landing, say), with focus untouched.
    await act(async () => bump());
    expect(document.activeElement).toBe(screen.getByText("d second"));
  });

  it("gives Esc to the innermost dialog only", async () => {
    const outer = vi.fn();
    const inner = vi.fn();
    render(
      <>
        <Dialog label="outer" onClose={outer} />
        <Dialog label="inner" onClose={inner} />
      </>,
    );
    await userEvent.keyboard("{Escape}");
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();
  });

  it("holds the scroll lock until the LAST dialog closes", () => {
    // Stable handlers, so nothing but the inner dialog's own close can touch the lock.
    const { rerender } = render(
      <>
        <Dialog key="outer" label="outer" onClose={noop} />
        <Dialog key="inner" label="inner" onClose={noop} />
      </>,
    );
    rerender(
      <>
        <Dialog key="outer" label="outer" onClose={noop} />
      </>,
    );
    expect(document.body.style.overflow).toBe("hidden");
    rerender(<></>);
    expect(document.body.style.overflow).toBe("");
  });
});
