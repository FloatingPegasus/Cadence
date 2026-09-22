import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import FocusPage from "./FocusPage";

describe("FocusPage", () => {
  it("shows the study scene, lo-fi control, and pomodoro", () => {
    render(<FocusPage />);
    screen.getByRole("heading", { name: "Focus" });
    screen.getByRole("button", { name: "Study scene" });
    screen.getByRole("button", { name: "Play lo-fi" });
    screen.getByRole("button", { name: "Start" });
    screen.getByRole("button", { name: "Cat, sleeping" });
    expect(screen.getByText("25:00")).toBeTruthy();
  });

  it("lets you pet the cat without changing the study scene", async () => {
    const user = userEvent.setup();
    render(<FocusPage />);
    expect(
      screen.getByRole("img", { name: "Tabby cat sleeping on a keyboard" }),
    ).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Cat, sleeping" }));
    screen.getByRole("button", { name: "Cat, purring" });
    expect(
      screen.getByRole("img", { name: "Tabby cat sleeping on a keyboard" }),
    ).toBeTruthy();
  });

  it("wakes the cat when a session starts", async () => {
    const user = userEvent.setup();
    render(<FocusPage />);
    await user.click(screen.getByRole("button", { name: "Start" }));
    expect(
      await screen.findByRole("button", { name: "Cat, sitting" }),
    ).toBeTruthy();
    expect(screen.getByText("25:00")).toBeTruthy();
  });

  it("lets you pick a background noise", async () => {
    const user = userEvent.setup();
    render(<FocusPage />);
    const picker = screen.getByRole("combobox", { name: "Background noise" });
    expect((picker as HTMLSelectElement).value).toBe("off");
    expect(screen.getByRole("option", { name: "No background noise" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Brown noise" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "White noise" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Rain" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Train" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Airplane" })).toBeTruthy();
    await user.selectOptions(picker, "rain");
    expect((picker as HTMLSelectElement).value).toBe("rain");
  });

  it("lets you pick pomodoro or a plain timer and open full screen", async () => {
    const user = userEvent.setup();
    render(<FocusPage />);
    const kind = screen.getByRole("combobox", { name: "Timer" });
    expect((kind as HTMLSelectElement).value).toBe("pomodoro");
    expect(screen.getByRole("option", { name: "Pomodoro" })).toBeTruthy();
    expect(screen.getByLabelText("Work minutes")).toBeTruthy();
    expect(screen.getByLabelText("Break minutes")).toBeTruthy();
    await user.selectOptions(kind, "timer");
    expect((kind as HTMLSelectElement).value).toBe("timer");
    expect(screen.getByLabelText("Minutes")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Full screen" }));
    const stage = screen.getByRole("dialog", { name: "Timer" });
    expect(stage.parentElement).toBe(document.body);
    expect(within(stage).getByRole("button", { name: /Cat/ })).toBeTruthy();
    expect(
      within(stage).getByRole("button", { name: "Play lo-fi" }),
    ).toBeTruthy();
    expect(
      within(stage).getByRole("combobox", { name: "Background noise" }),
    ).toBeTruthy();
    const panel = stage.querySelector(".cadence-timer-float");
    expect(panel).toBeTruthy();
    vi.spyOn(stage, "getBoundingClientRect").mockReturnValue({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 800,
      bottom: 800,
      width: 800,
      height: 800,
      toJSON() {
        return {};
      },
    });
    vi.spyOn(panel as HTMLElement, "getBoundingClientRect").mockReturnValue({
      x: 250,
      y: 200,
      top: 200,
      left: 250,
      right: 650,
      bottom: 500,
      width: 400,
      height: 300,
      toJSON() {
        return {};
      },
    });
    Object.defineProperty(panel, "offsetWidth", { value: 400 });
    Object.defineProperty(panel, "offsetHeight", { value: 300 });

    const handle = screen.getByRole("button", { name: "Move timer" });
    fireEvent.pointerDown(handle, {
      pointerId: 1,
      button: 0,
      clientX: 400,
      clientY: 220,
    });
    fireEvent.pointerMove(window, {
      pointerId: 1,
      clientX: 500,
      clientY: 320,
    });
    expect((panel as HTMLElement).style.left).toBe("350px");
    expect((panel as HTMLElement).style.top).toBe("300px");
    fireEvent.pointerUp(window, { pointerId: 1 });
    handle.focus();
    fireEvent.keyDown(handle, { key: "ArrowUp" });
    expect((panel as HTMLElement).style.top).toBe("284px");

    const resize = screen.getByRole("button", {
      name: "Resize from bottom right",
    });
    fireEvent.pointerDown(resize, {
      pointerId: 2,
      button: 0,
      clientX: 640,
      clientY: 490,
    });
    fireEvent.pointerMove(window, {
      pointerId: 2,
      clientX: 690,
      clientY: 530,
    });
    expect((panel as HTMLElement).style.width).toBe("450px");
    expect((panel as HTMLElement).style.height).toBe("340px");
    fireEvent.pointerUp(window, { pointerId: 2 });

    await user.click(screen.getByRole("button", { name: "Exit full screen" }));
    expect(screen.queryByRole("dialog", { name: "Timer" })).toBeNull();
  });

  it("uses icons when the fullscreen timer is too narrow for labels", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        callback: ResizeObserverCallback;
        constructor(callback: ResizeObserverCallback) {
          this.callback = callback;
        }
        observe(target: Element) {
          this.callback(
            [
              {
                target,
                contentRect: {
                  x: 0,
                  y: 0,
                  top: 0,
                  left: 0,
                  right: 230,
                  bottom: 320,
                  width: 230,
                  height: 320,
                  toJSON() {
                    return {};
                  },
                },
                borderBoxSize: [],
                contentBoxSize: [],
                devicePixelContentBoxSize: [],
              },
            ],
            this,
          );
        }
        unobserve() {}
        disconnect() {}
      },
    );
    const user = userEvent.setup();
    render(<FocusPage />);
    await user.click(screen.getByRole("button", { name: "Full screen" }));
    const stage = screen.getByRole("dialog", { name: "Timer" });
    await waitFor(() =>
      expect(
        stage.querySelector(".cadence-timer-float")?.getAttribute("data-density"),
      ).toBe("icon"),
    );
    expect(
      within(stage).getByRole("button", { name: "Start" }).querySelector("svg"),
    ).toBeTruthy();
    expect(
      within(stage).getByRole("button", { name: "Reset" }).querySelector("svg"),
    ).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it("keeps labels when the fullscreen timer is wide enough", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        callback: ResizeObserverCallback;
        constructor(callback: ResizeObserverCallback) {
          this.callback = callback;
        }
        observe(target: Element) {
          this.callback(
            [
              {
                target,
                contentRect: {
                  x: 0,
                  y: 0,
                  top: 0,
                  left: 0,
                  right: 480,
                  bottom: 520,
                  width: 480,
                  height: 520,
                  toJSON() {
                    return {};
                  },
                },
                borderBoxSize: [],
                contentBoxSize: [],
                devicePixelContentBoxSize: [],
              },
            ],
            this,
          );
        }
        unobserve() {}
        disconnect() {}
      },
    );
    const user = userEvent.setup();
    render(<FocusPage />);
    await user.click(screen.getByRole("button", { name: "Full screen" }));
    const stage = screen.getByRole("dialog", { name: "Timer" });
    await waitFor(() =>
      expect(
        stage.querySelector(".cadence-timer-float")?.getAttribute("data-density"),
      ).toBe("full"),
    );
    expect(
      stage.querySelector(".cadence-timer-float")?.getAttribute("data-tall"),
    ).toBe("true");
    vi.unstubAllGlobals();
  });

  it("lets you replace minutes and restores them if left empty", async () => {
    const user = userEvent.setup();
    render(<FocusPage />);
    const input = screen.getByLabelText("Work minutes") as HTMLInputElement;
    await user.clear(input);
    expect(input.value).toBe("");
    await user.type(input, "50");
    expect(input.value).toBe("50");
    await user.tab();
    expect(input.value).toBe("50");
    expect(screen.getByText("50:00")).toBeTruthy();

    await user.clear(input);
    expect(input.value).toBe("");
    await user.tab();
    expect(input.value).toBe("50");
    expect(screen.getByRole("alert").textContent).toBe("Enter minutes");
  });

  it("opens a landscape picture-in-picture of the study scene", async () => {
    const pipDocument = document.implementation.createHTMLDocument("pip");
    const pipWindow = {
      document: pipDocument,
      close: vi.fn(),
      addEventListener: vi.fn(),
    };
    const requestWindow = vi.fn().mockResolvedValue(pipWindow);
    Object.defineProperty(window, "documentPictureInPicture", {
      configurable: true,
      value: { requestWindow },
    });
    const user = userEvent.setup();
    render(<FocusPage />);
    await user.click(screen.getByRole("button", { name: "Full screen" }));
    await user.click(screen.getByRole("button", { name: "Picture in picture" }));
    await waitFor(() =>
      expect(pipDocument.body.querySelector(".cadence-timer-pip")).toBeTruthy(),
    );
    expect(requestWindow).toHaveBeenCalledWith({ width: 720, height: 405 });
    expect(pipDocument.documentElement.classList.contains("cadence-pip")).toBe(
      true,
    );
    expect(
      pipDocument.body.querySelector(".cadence-timer-pip-clock")?.textContent,
    ).toBe("25:00");
    expect(
      pipDocument.body.querySelector('[aria-label="Study scene"]'),
    ).toBeTruthy();
    expect(pipDocument.body.querySelector(".cadence-timer-controls")).toBeNull();
    expect(screen.queryByRole("dialog", { name: "Timer" })).toBeNull();
  });
});
