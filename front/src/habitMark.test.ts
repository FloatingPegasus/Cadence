import { describe, expect, it } from "vitest";

import { habitMarkClass } from "./habitMark";

describe("habitMarkClass", () => {
  it("gives neighboring ids different marks", () => {
    expect(habitMarkClass(1)).toBe("habit-mark-1");
    expect(habitMarkClass(2)).toBe("habit-mark-2");
    expect(habitMarkClass(1)).not.toBe(habitMarkClass(2));
  });

  it("repeats after six habits", () => {
    expect(habitMarkClass(7)).toBe(habitMarkClass(1));
  });
});
