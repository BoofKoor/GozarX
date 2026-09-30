import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useCommandPaletteShortcut } from "./CommandPalette";

function Harness({ onOpen }: { onOpen: () => void }) {
  useCommandPaletteShortcut(onOpen);
  return (
    <div>
      <textarea aria-label="composer" />
      <input aria-label="search" />
      <button type="button">plain</button>
    </div>
  );
}

describe("useCommandPaletteShortcut", () => {
  it("opens from anywhere that is not a text field", () => {
    const onOpen = vi.fn();
    const { getByText } = render(<Harness onOpen={onOpen} />);
    fireEvent.keyDown(getByText("plain"), { key: "k", ctrlKey: true });
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("stays out of the way while the operator is typing", () => {
    // Ctrl+K then Enter in the broadcast composer opened the palette, picked its first entry and
    // navigated away — taking the unsaved message with it.
    const onOpen = vi.fn();
    const { getByLabelText } = render(<Harness onOpen={onOpen} />);
    fireEvent.keyDown(getByLabelText("composer"), { key: "k", ctrlKey: true });
    fireEvent.keyDown(getByLabelText("search"), { key: "k", metaKey: true });
    expect(onOpen).not.toHaveBeenCalled();
  });
});
