import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { authStub } from "../authTest";
import { useAuth } from "../contexts/AuthContext";
import AIPrivacySettings from "./AIPrivacySettings";

vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

describe("AIPrivacySettings", () => {
  it("requires an explicit save before automatic summary settings change", async () => {
    const user = userEvent.setup();
    const updateAIPrivacy = vi.fn().mockResolvedValue({});
    vi.mocked(useAuth).mockReturnValue(authStub({ updateAIPrivacy }));

    render(<AIPrivacySettings />);
    await user.click(
      screen.getByRole("checkbox", {
        name: /Let Cadence reply to logs/,
      }),
    );
    expect(updateAIPrivacy).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Save AI preferences" }),
    );
    expect(updateAIPrivacy).toHaveBeenCalledWith(true, true);
  });
});
