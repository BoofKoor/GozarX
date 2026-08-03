import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver, and recharts' <ResponsiveContainer> constructs one on mount — so any
// test that renders a chart throws before a single assertion runs. A no-op stub is enough: the
// container falls back to its default size, which is all these tests need.
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
