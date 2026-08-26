import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

const values = new Map<string, string>();

const localStorageShim: Storage = {
  get length() {
    return values.size;
  },
  clear() {
    values.clear();
  },
  getItem(key: string) {
    return values.get(key) ?? null;
  },
  key(index: number) {
    return Array.from(values.keys())[index] ?? null;
  },
  removeItem(key: string) {
    values.delete(key);
  },
  setItem(key: string, value: string) {
    values.set(key, value);
  },
};

Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: localStorageShim,
});

function clearCookies(): void {
  for (const part of document.cookie.split(";")) {
    const name = part.trim().split("=", 1)[0];
    if (name) {
      document.cookie = `${name}=; Max-Age=0; path=/`;
    }
  }
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  clearCookies();
});
