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

describe("useFocusTrap", () => {
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
