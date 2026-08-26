import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import FocusPage from "./FocusPage";

describe("FocusPage", () => {
  it("shows the study scene, lo-fi control, and pomodoro", () => {
    render(<FocusPage />);
    screen.getByRole("heading", { name: "Focus" });
    screen.getByRole("img", {
      name: "A cat at a study desk by a rainy window",
    });
    screen.getByRole("button", { name: "Play lo-fi" });
    screen.getByRole("button", { name: "Start" });
    expect(screen.getByText("25:00")).toBeTruthy();
  });
});
