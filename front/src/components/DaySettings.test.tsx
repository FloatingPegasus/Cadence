import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { authStub, testUser } from "../authTest";
import { useAuth } from "../contexts/AuthContext";
import DaySettings from "./DaySettings";

vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

describe("DaySettings", () => {
  it("saves the day boundary and auto close as soon as they change", async () => {
    const user = userEvent.setup();
    const updateDaySettings = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue(
      authStub({ user: { ...testUser, day_ends_at: 4 }, updateDaySettings }),
    );
    render(<DaySettings />);

    const boundary = screen.getByRole("combobox", { name: "Day ends at" });
    expect((boundary as HTMLSelectElement).value).toBe("4");
    await user.selectOptions(boundary, "2");
    expect(updateDaySettings).toHaveBeenLastCalledWith({
      day_ends_at: 2,
      auto_close: true,
    });

    await user.click(
      screen.getByRole("checkbox", { name: "Close past days by themselves" }),
    );
    expect(updateDaySettings).toHaveBeenLastCalledWith({
      day_ends_at: 4,
      auto_close: false,
    });
  });
});
