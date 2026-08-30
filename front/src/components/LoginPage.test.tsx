import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { useAuth } from "../contexts/AuthContext";
import LoginPage from "./LoginPage";

vi.mock("../contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

describe("LoginPage verification recovery", () => {
  it("requests a fresh verification message by email", async () => {
    const user = userEvent.setup();
    const resendVerification = vi.fn().mockResolvedValue(
      "If an unverified account uses that email, a new verification message has been sent.",
    );
    mockedUseAuth.mockReturnValue({
      user: null,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      resendVerification,
      updateAIPrivacy: vi.fn(),
      verifyEmail: vi.fn(),
      logout: vi.fn(),
    });

    render(<LoginPage />);
    screen.getByText("Habits, hours, and a focus room.");
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
    await screen.findByRole("heading", { name: "Check your email" });
    screen.getByText("Link sent to pending@example.com.");
    expect(
      screen.queryByText("Habits, hours, and a focus room."),
    ).toBeNull();
  });

  it("shows where the verification link went after register", async () => {
    const user = userEvent.setup();
    const register = vi.fn().mockResolvedValue({
      id: 1,
      username: "kai",
      email: "kai@example.com",
      is_verified: false,
      message:
        "Account created. Check your email to verify your address before logging in.",
    });
    const resendVerification = vi.fn().mockResolvedValue(
      "If an unverified account uses that email, a new verification message has been sent.",
    );
    mockedUseAuth.mockReturnValue({
      user: null,
      isLoading: false,
      login: vi.fn(),
      register,
      resendVerification,
      updateAIPrivacy: vi.fn(),
      verifyEmail: vi.fn(),
      logout: vi.fn(),
    });

    render(<LoginPage />);
    await user.click(
      screen.getByRole("button", { name: "Need an account? Register" }),
    );
    await user.type(screen.getByRole("textbox", { name: "Username" }), "kai");
    await user.type(
      screen.getByRole("textbox", { name: "Email" }),
      "kai@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "a-strong-password");
    await user.click(screen.getByRole("button", { name: "Register" }));

    await screen.findByRole("heading", { name: "Check your email" });
    screen.getByText("Link sent to kai@example.com.");
    expect(
      screen.queryByText("Habits, hours, and a focus room."),
    ).toBeNull();
    await user.click(screen.getByRole("button", { name: "Send again" }));
    expect(resendVerification).toHaveBeenCalledWith("kai@example.com");
    await screen.findByRole("button", { name: "Sent again" });
  });

  it("accepts an email address for login", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: null,
      isLoading: false,
      login,
      register: vi.fn(),
      resendVerification: vi.fn(),
      updateAIPrivacy: vi.fn(),
      verifyEmail: vi.fn(),
      logout: vi.fn(),
    });

    render(<LoginPage />);
    await user.type(
      screen.getByRole("textbox", { name: "Username or email" }),
      "dev@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "local-dev-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(login).toHaveBeenCalledWith(
      "dev@example.com",
      "local-dev-password",
    );
  });
});
