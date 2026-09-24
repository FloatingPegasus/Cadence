import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { authStub, testUser } from "../authTest";
import { useAuth } from "../contexts/AuthContext";
import { ThemeProvider } from "../contexts/ThemeContext";
import Header from "./Header";

vi.mock("../contexts/AuthContext", () => ({ useAuth: vi.fn() }));

function renderHeader(onOpenSettings = vi.fn()) {
  return render(
    <ThemeProvider>
      <Header settingsOpen={false} onOpenSettings={onOpenSettings} />
    </ThemeProvider>,
  );
}

describe("Header", () => {
  it("keeps theme and username without a log out action", () => {
    vi.mocked(useAuth).mockReturnValue(authStub());

    renderHeader();

    expect(screen.getByText("alpha")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Dark" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Log out" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Log in" })).toBeNull();
  });

  it("opens settings from the header", async () => {
    const user = userEvent.setup();
    const onOpenSettings = vi.fn();
    vi.mocked(useAuth).mockReturnValue(authStub());
    renderHeader(onOpenSettings);
    await user.click(screen.getByRole("button", { name: "Settings" }));
    expect(onOpenSettings).toHaveBeenCalledOnce();
  });

  it("offers log in with no session", () => {
    vi.mocked(useAuth).mockReturnValue(authStub({ user: null }));
    renderHeader();
    expect(screen.getByRole("button", { name: "Log in" })).toBeTruthy();
  });

  it("closes the log in dialog from its close button", async () => {
    const user = userEvent.setup();
    const closeAuth = vi.fn();
    vi.mocked(useAuth).mockReturnValue(
      authStub({ user: null, authDialog: "login", closeAuth }),
    );
    renderHeader();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(closeAuth).toHaveBeenCalledOnce();
  });

  it("offers keep this for a guest", async () => {
    const user = userEvent.setup();
    const openClaim = vi.fn();
    vi.mocked(useAuth).mockReturnValue(
      authStub({
        user: { ...testUser, is_guest: true, email: null, username: "guest-aa" },
        openClaim,
      }),
    );
    renderHeader();
    await user.click(screen.getByRole("button", { name: "Keep this" }));
    expect(openClaim).toHaveBeenCalledOnce();
    expect(screen.queryByText("guest-aa")).toBeNull();
  });
});
