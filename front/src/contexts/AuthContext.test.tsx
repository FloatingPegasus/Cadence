import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { request } from "../api";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../api", () => ({
  request: vi.fn(),
  updateAIPreferences: vi.fn(),
  setWriteSessionGate: vi.fn(),
}));

const mockedRequest = vi.mocked(request);

function sessionRequests(user: { username: string } | null) {
  mockedRequest.mockImplementation((input) => {
    const url = String(input);
    if (url === "/api/auth/options") {
      return Promise.resolve({ allow_guests: false });
    }
    if (url === "/api/auth/me") {
      return user
        ? Promise.resolve(user)
        : Promise.reject(new Error("Not authenticated"));
    }
    return Promise.reject(new Error(`unexpected ${url}`));
  });
}

function SessionProbe() {
  const { isLoading, user } = useAuth();
  return (
    <div>
      <span>{isLoading ? "loading" : "ready"}</span>
      <span>{user?.username ?? "anonymous"}</span>
    </div>
  );
}

function LogoutProbe() {
  const { logout, user } = useAuth();
  return (
    <div>
      <span>{user?.username ?? "anonymous"}</span>
      <button type="button" onClick={() => void logout().catch(() => {})}>
        log out
      </button>
    </div>
  );
}

describe("AuthProvider session restore", () => {
  it("keeps the app behind an initial loading state", async () => {
    let resolveSession: (user: { username: string }) => void = () => {};
    mockedRequest.mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/options") {
        return Promise.resolve({ allow_guests: false });
      }
      if (url === "/api/auth/me") {
        return new Promise((resolve) => {
          resolveSession = resolve;
        });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });

    render(
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>,
    );

    screen.getByText("loading");
    screen.getByText("anonymous");

    resolveSession({ username: "alpha" });
    await waitFor(() => screen.getByText("ready"));
    screen.getByText("alpha");
  });

  it("keeps the user on logout failure", async () => {
    const user = userEvent.setup();
    sessionRequests({ username: "alpha" });
    render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );
    await waitFor(() => screen.getByText("alpha"));

    mockedRequest.mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/logout") {
        return Promise.reject(new Error("logout failed"));
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    await user.click(screen.getByRole("button", { name: "log out" }));

    screen.getByText("alpha");
  });

  it("clears the user only after logout succeeds", async () => {
    const user = userEvent.setup();
    sessionRequests({ username: "alpha" });
    render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );
    await waitFor(() => screen.getByText("alpha"));

    mockedRequest.mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/logout") {
        return Promise.resolve({ message: "Logged out" });
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    await user.click(screen.getByRole("button", { name: "log out" }));

    await waitFor(() => screen.getByText("anonymous"));
  });
});
