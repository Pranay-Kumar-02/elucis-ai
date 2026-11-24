import { describe, expect, it } from "vitest";

import { normaliseBaseUrl } from "@/lib/env";

describe("normaliseBaseUrl", () => {
  it("defaults to same origin", () => {
    expect(normaliseBaseUrl(undefined)).toBe("");
    expect(normaliseBaseUrl("  ")).toBe("");
  });

  it("strips trailing slashes", () => {
    expect(normaliseBaseUrl("http://127.0.0.1:8000/")).toBe("http://127.0.0.1:8000");
  });

  it("rejects relative or non-http URLs", () => {
    expect(() => normaliseBaseUrl("api.local")).toThrow(/absolute URL/);
    expect(() => normaliseBaseUrl("ftp://host")).toThrow(/http or https/);
  });
});
