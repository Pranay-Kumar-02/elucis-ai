import { describe, expect, it } from "vitest";

import { formatBytes, formatOccurredAt } from "@/features/sources/format";

describe("formatOccurredAt", () => {
  it("keeps date-only values on their calendar date in every time zone", () => {
    const text = formatOccurredAt("2026-12-25T00:00:00Z", "25/12/2026");
    expect(text).toContain("25");
    expect(text).not.toMatch(/\d:\d{2}/);
  });

  it("shows a time when the source had one", () => {
    expect(formatOccurredAt("2026-12-25T09:14:00Z", "2026-12-25 09:14")).toMatch(/\d:\d{2}/);
  });
});

describe("formatBytes", () => {
  it("uses readable units", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});
