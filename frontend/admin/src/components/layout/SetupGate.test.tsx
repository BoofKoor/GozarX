import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { useSetupStatus } from "@/hooks/useSetup";

import { SetupGate } from "./SetupGate";

vi.mock("@/hooks/useSetup", () => ({ useSetupStatus: vi.fn() }));

function renderGate() {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route element={<SetupGate />}>
          <Route path="/" element={<div>SHELL</div>} />
        </Route>
        <Route path="/setup" element={<div>WIZARD</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SetupGate", () => {
  it("redirects to /setup when setup is not completed", () => {
    vi.mocked(useSetupStatus).mockReturnValue({
      data: { completed: false },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useSetupStatus>);
    renderGate();
    expect(screen.getByText("WIZARD")).toBeInTheDocument();
  });

  it("renders the shell when setup is completed", () => {
    vi.mocked(useSetupStatus).mockReturnValue({
      data: { completed: true },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useSetupStatus>);
    renderGate();
    expect(screen.getByText("SHELL")).toBeInTheDocument();
  });
});
