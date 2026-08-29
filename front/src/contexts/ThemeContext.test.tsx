import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ThemeProvider, useTheme } from "./ThemeContext";

function Toggle() {
  const { theme, setTheme } = useTheme();
  return (
    <button
      type="button"
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
    >
      {theme === "light" ? "Dark" : "Light"}
    </button>
  );
}

describe("theme", () => {
  it("starts light and can switch to dark", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <Toggle />
      </ThemeProvider>,
    );

    expect(screen.getByRole("button", { name: "Dark" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByRole("button", { name: "Light" })).toBeTruthy();
  });
});
