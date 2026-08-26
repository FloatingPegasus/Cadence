import { describe, expect, it, vi } from "vitest";

import { request } from "./api";

function jsonResponse(body: unknown = { ok: true }, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function setCsrfCookie(value = "csrf-value"): void {
  document.cookie = `cadence_csrf=${encodeURIComponent(value)}; path=/`;
}

describe("cookie-authenticated API requests", () => {
  it("strips supplied bearer credentials and uses the CSRF cookie", async () => {
    setCsrfCookie();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse());
    const body = JSON.stringify({ daily_note: "local" });

    await request("/api/days/2026-08-14", {
      method: "PUT",
      headers: {
        Authorization: "Bearer stale-token",
        "X-CSRF-Token": "stale-csrf",
      },
      body,
    });

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(init?.credentials).toBe("include");
    expect(init?.body).toBe(body);
    expect(headers.get("Authorization")).toBeNull();
    expect(headers.get("X-CSRF-Token")).toBe("csrf-value");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"] as const)(
    "sends the CSRF cookie for %s requests",
    async (method) => {
      setCsrfCookie();
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(jsonResponse());

      await request("/api/resource", {
        method,
        body: JSON.stringify({ method }),
      });

      const [, init] = fetchMock.mock.calls[0];
      expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe(
        "csrf-value",
      );
    },
  );

  it.each(["GET", "HEAD", "OPTIONS"] as const)(
    "does not send CSRF for %s requests",
    async (method) => {
      setCsrfCookie();
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(jsonResponse());

      await request("/api/resource", { method });

      const [, init] = fetchMock.mock.calls[0];
      expect(new Headers(init?.headers).get("X-CSRF-Token")).toBeNull();
      expect(init?.credentials).toBe("include");
    },
  );

  it("keeps form bodies intact without forcing a JSON content type", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => jsonResponse());
    const form = new FormData();
    form.set("note", "local");

    await request("/api/upload", { method: "POST", body: form });

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(init?.body).toBe(form);
    expect(headers.get("Content-Type")).toBeNull();
  });

  it("surfaces a JSON detail from a non-2xx response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(
        { detail: "The request was rejected" },
        { status: 422, statusText: "Unprocessable Entity" },
      ),
    );

    await expect(request("/api/resource")).rejects.toThrow(
      "The request was rejected",
    );
  });

  it("falls back to status text when an error body is not JSON", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("not-json", {
        status: 503,
        statusText: "Service Unavailable",
      }),
    );

    await expect(request("/api/resource")).rejects.toThrow(
      "Service Unavailable",
    );
  });

  it("removes the legacy browser token during module initialization", async () => {
    window.localStorage.setItem("cadence_token", "legacy-token");
    vi.resetModules();

    await import("./api");

    expect(window.localStorage.getItem("cadence_token")).toBeNull();
  });
});
