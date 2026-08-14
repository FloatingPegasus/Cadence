import { afterEach, describe, expect, it, vi } from "vitest";

import { request } from "./api";

describe("cookie-authenticated API requests", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.cookie = "cadence_csrf=; Max-Age=0; path=/";
    window.localStorage.removeItem("cadence_token");
  });

  it("includes credentials and the readable CSRF cookie without a bearer token", async () => {
    document.cookie = "cadence_csrf=csrf-value; path=/";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    await request("/api/days/2026-08-14", {
      method: "PUT",
      body: JSON.stringify({ daily_note: "local" }),
    });

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(init?.credentials).toBe("include");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-value");
    expect(headers.get("Authorization")).toBeNull();
  });

  it("does not send a CSRF header for safe requests", async () => {
    document.cookie = "cadence_csrf=csrf-value; path=/";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    await request("/api/auth/me");

    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBeNull();
    expect(init?.credentials).toBe("include");
  });

  it("removes the legacy browser token during module initialization", async () => {
    window.localStorage.setItem("cadence_token", "legacy-token");
    vi.resetModules();

    await import("./api");

    expect(window.localStorage.getItem("cadence_token")).toBeNull();
  });
});
