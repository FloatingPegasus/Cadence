import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchDataExport } from "../api";
import DataExportButton from "./DataExportButton";

vi.mock("../api", () => ({
  fetchDataExport: vi.fn(),
}));

const fetchExport = vi.mocked(fetchDataExport);

describe("DataExportButton", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:cadence-export"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("downloads the authenticated account export", async () => {
    const user = userEvent.setup();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    fetchExport.mockResolvedValue({
      format: "cadence-export",
      schema_version: 1,
      exported_at: "2026-07-24T00:00:00+00:00",
      account: {
        username: "alpha",
        email: "alpha@example.com",
        is_verified: true,
      },
      resources: { days: [] },
    });

    render(<DataExportButton />);
    await user.click(screen.getByRole("button", { name: "Export data" }));

    expect(fetchExport).toHaveBeenCalledOnce();
    expect(URL.createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(
      "blob:cadence-export",
    );
  });

  it("shows export failures without losing the action", async () => {
    const user = userEvent.setup();
    fetchExport.mockRejectedValue(new Error("Export unavailable"));

    render(<DataExportButton />);
    await user.click(screen.getByRole("button", { name: "Export data" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Export unavailable",
    );
    expect(
      (
        screen.getByRole("button", {
          name: "Export data",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });
});
