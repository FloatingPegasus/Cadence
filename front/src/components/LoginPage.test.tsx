import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { authStub } from "../authTest";
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
    mockedUseAuth.mockReturnValue(
      authStub({ user: null, resendVerification }),
    );

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
    await screen.findByRole("heading", { name: "Check your email" });
    screen.getByText("Link sent to pending@example.com.");
  });

  it("signs in after register", async () => {
    const user = userEvent.setup();
    const onFinished = vi.fn();
    const register = vi.fn().mockResolvedValue({
      id: 1,
      username: "kai",
      email: "kai@example.com",
      is_verified: false,
      is_guest: false,
      message: "Account created. Check your email to verify your address.",
    });
    mockedUseAuth.mockReturnValue(authStub({ user: null, register }));

    render(<LoginPage onFinished={onFinished} />);
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

    expect(register).toHaveBeenCalledWith(
      "kai",
      "kai@example.com",
      "a-strong-password",
    );
    expect(onFinished).toHaveBeenCalledOnce();
  });

  it("accepts an email address for login", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue(authStub({ user: null, login }));

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

  it("claims a guest session", async () => {
    const user = userEvent.setup();
    const claim = vi.fn().mockResolvedValue(undefined);
    const onFinished = vi.fn();
    mockedUseAuth.mockReturnValue(authStub({ user: null, claim }));

    render(<LoginPage intent="claim" onFinished={onFinished} />);
    await user.type(screen.getByRole("textbox", { name: "Username" }), "kai");
    await user.type(
      screen.getByRole("textbox", { name: "Email" }),
      "kai@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "a-strong-password");
    await user.click(screen.getByRole("button", { name: "Keep this" }));

    expect(claim).toHaveBeenCalledWith(
      "kai",
      "kai@example.com",
      "a-strong-password",
    );
    expect(onFinished).toHaveBeenCalledOnce();
  });
});
