import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useAuth } from "../contexts/AuthContext";
import { ThemeProvider } from "../contexts/ThemeContext";
import Header from "./Header";

vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

describe("Header", () => {
  it("keeps theme and username without a log out action", () => {
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
      logout: vi.fn(),
    });

    render(
      <ThemeProvider>
        <Header />
      </ThemeProvider>,
    );

    expect(screen.getByText("alpha")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Dark" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Log out" })).toBeNull();
  });
});
