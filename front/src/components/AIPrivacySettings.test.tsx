import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { useAuth } from "../contexts/AuthContext";
import AIPrivacySettings from "./AIPrivacySettings";

vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

describe("AIPrivacySettings", () => {
  it("requires an explicit save before automatic summary settings change", async () => {
    const user = userEvent.setup();
    const updateAIPrivacy = vi.fn().mockResolvedValue({});
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        username: "alpha",
        email: "alpha@example.com",
        is_verified: true,
        is_developer: false,
        ai_processing_consent: false,
        ai_redaction_enabled: true,
      },
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      resendVerification: vi.fn(),
      updateAIPrivacy,
      verifyEmail: vi.fn(),
      logout: vi.fn(),
    });

    render(<AIPrivacySettings />);
    await user.click(
      screen.getByRole("checkbox", {
        name: /Allow automatic summaries/,
      }),
    );
    expect(updateAIPrivacy).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Save AI preferences" }),
    );
    expect(updateAIPrivacy).toHaveBeenCalledWith(true, true);
  });
});
