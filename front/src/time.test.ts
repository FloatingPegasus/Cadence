import { afterEach, describe, expect, it, vi } from "vitest";

import { setDayEndsAt, todayAsLocalDate } from "./time";

describe("todayAsLocalDate", () => {
  afterEach(() => {
    setDayEndsAt(0);
    vi.useRealTimers();
  });

  it("counts the small hours toward the previous day", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 6, 24, 1, 30));

    expect(todayAsLocalDate()).toBe("2026-07-24");
    setDayEndsAt(4);
    expect(todayAsLocalDate()).toBe("2026-07-23");

    vi.setSystemTime(new Date(2026, 6, 24, 4, 0));
    expect(todayAsLocalDate()).toBe("2026-07-24");
  });
});
