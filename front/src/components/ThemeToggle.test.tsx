import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ThemeProvider } from "../contexts/ThemeContext";
import ThemeToggle from "./ThemeToggle";

describe("ThemeToggle", () => {
  it("uses a moon or sun instead of a text label", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const toggle = screen.getByRole("button", { name: "Dark" });
    expect(toggle.querySelector("svg")).toBeTruthy();
    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Light" }).querySelector("svg")).toBeTruthy();
  });
});
