import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { useAuth } from "../contexts/AuthContext";
import LogoutButton from "./LogoutButton";

vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

describe("LogoutButton", () => {
  it("logs out when clicked", async () => {
    const user = userEvent.setup();
    const logout = vi.fn().mockResolvedValue(undefined);
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
      updateAIPrivacy: vi.fn(),
      verifyEmail: vi.fn(),
      logout,
    });

    render(<LogoutButton />);
    await user.click(screen.getByRole("button", { name: "Log out" }));
    expect(logout).toHaveBeenCalledOnce();
  });

  it("shows logout failures without leaving the button", async () => {
    const user = userEvent.setup();
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
      updateAIPrivacy: vi.fn(),
      verifyEmail: vi.fn(),
      logout: vi.fn().mockRejectedValue(new Error("logout failed")),
    });

    render(<LogoutButton />);
    await user.click(screen.getByRole("button", { name: "Log out" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "logout failed",
    );
    expect(screen.getByRole("button", { name: "Log out" })).toBeTruthy();
  });
});
