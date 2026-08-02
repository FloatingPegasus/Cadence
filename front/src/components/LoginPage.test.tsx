import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "../contexts/AuthContext";
import LoginPage from "./LoginPage";

vi.mock("../contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

describe("LoginPage verification recovery", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("requests a fresh verification message by email", async () => {
    const user = userEvent.setup();
    const resendVerification = vi.fn().mockResolvedValue(
      "If an unverified account uses that email, a new verification message has been sent.",
    );
    mockedUseAuth.mockReturnValue({
      token: null,
      user: null,
      login: vi.fn(),
      register: vi.fn(),
      resendVerification,
      updateAIPrivacy: vi.fn(),
      verifyEmail: vi.fn(),
      logout: vi.fn(),
    });

    render(<LoginPage />);
    await user.click(
      screen.getByRole("button", {
        name: "Resend verification email",
      }),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Email" }),
      "pending@example.com",
    );
    await user.click(
      screen.getByRole("button", { name: "Resend verification" }),
    );

    expect(resendVerification).toHaveBeenCalledWith(
      "pending@example.com",
    );
    expect(
      await screen.findByText(/new verification message has been sent/),
    ).toBeTruthy();
  });
});
