import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import FocusCat from "./FocusCat";

function renderCat(running = false) {
  const { container } = render(
    <div style={{ position: "relative", width: 800, height: 400 }}>
      <FocusCat clock="24:12" running={running} />
    </div>,
  );
  const host = container.querySelector(".cadence-focus-cat-stage");
  const cat = screen.getByRole("button", { name: /Cat/ });
  if (host instanceof HTMLElement) {
    vi.spyOn(host, "getBoundingClientRect").mockReturnValue({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 800,
      bottom: 400,
      width: 800,
      height: 400,
      toJSON() {
        return {};
      },
    });
  }
  Object.defineProperty(cat, "offsetWidth", { value: 81 });
  Object.defineProperty(cat, "offsetHeight", { value: 87 });
  return cat as HTMLButtonElement;
}

describe("FocusCat", () => {
  it("sleeps until you pet it", async () => {
    const user = userEvent.setup();
    renderCat();
    const cat = screen.getByRole("button", { name: "Cat, sleeping" });
    expect(cat.querySelector("img")?.getAttribute("src")).toBe(
      "/focus/companion-sleep.png",
    );
    await user.click(cat);
    screen.getByRole("button", { name: "Cat, purring" });
    expect(cat.querySelector("img")?.getAttribute("src")).toBe(
      "/focus/companion-sit.png",
    );
  });

  it("shows remaining time while a session is running", () => {
    renderCat(true);
    screen.getByRole("button", { name: "Cat, 24:12" });
    expect(screen.getByText("24:12")).toBeTruthy();
  });

  it("can be dragged to a new spot", () => {
    const cat = renderCat();
    vi.spyOn(cat, "getBoundingClientRect").mockReturnValue({
      x: 64,
      y: 284,
      top: 284,
      left: 64,
      right: 145,
      bottom: 371,
      width: 81,
      height: 87,
      toJSON() {
        return {};
      },
    });
    fireEvent.pointerDown(cat, {
      pointerId: 1,
      button: 0,
      clientX: 80,
      clientY: 300,
    });
    fireEvent.pointerMove(cat, {
      pointerId: 1,
      clientX: 240,
      clientY: 250,
    });
    expect(cat.style.left).toBe("28%");
    expect(cat.style.bottom).toBe("19.75%");
    fireEvent.pointerUp(cat, { pointerId: 1 });
    expect(screen.getByRole("button", { name: "Cat, sitting" })).toBeTruthy();
  });
});
