import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, apiUrl } from "@/lib/api/client";
import { json, mockFetch } from "@/test/utils";

describe("apiUrl", () => {
  it("prefixes the versioned API path", () => {
    expect(apiUrl("/health")).toBe("/api/v1/health");
    expect(apiUrl("health")).toBe("/api/v1/health");
  });
});

describe("apiRequest", () => {
  it("returns parsed JSON and sends credentials", async () => {
    const fetchMock = mockFetch({ "/api/v1/health/live": () => json({ status: "ok" }) });
    await expect(apiRequest("/health/live")).resolves.toEqual({ status: "ok" });
    const init = fetchMock.mock.calls[0]?.[1];
    expect(init?.credentials).toBe("include");
  });

  it("throws ApiError from the error envelope", async () => {
    mockFetch({
      "/api/v1/x": () =>
        json(
          {
            error: {
              code: "validation_failed",
              message: "Bad input.",
              details: [{ field: "text", issue: "required" }],
              request_id: "01ABC",
            },
          },
          422,
        ),
    });
    const error = await apiRequest("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      code: "validation_failed",
      message: "Bad input.",
      requestId: "01ABC",
      details: [{ field: "text", issue: "required" }],
    });
  });

  it("accepts listed non-2xx statuses as data", async () => {
    mockFetch({ "/api/v1/health": () => json({ status: "unavailable" }, 503) });
    await expect(apiRequest("/health", { acceptStatuses: [503] })).resolves.toEqual({
      status: "unavailable",
    });
  });

  it("maps a non-envelope error to unexpected_response", async () => {
    mockFetch({ "/api/v1/x": () => new Response("<html>bad gateway</html>", { status: 502 }) });
    await expect(apiRequest("/x")).rejects.toMatchObject({
      code: "unexpected_response",
      status: 502,
    });
  });

  it("maps network failures to network_error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );
    await expect(apiRequest("/x")).rejects.toMatchObject({ code: "network_error", status: 0 });
  });

  it("sends JSON bodies with a content type and FormData untouched", async () => {
    const fetchMock = mockFetch({ "/api/v1/echo": () => json({}) });
    await apiRequest("/echo", { method: "POST", body: { a: 1 } });
    const jsonInit = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(jsonInit?.headers).get("content-type")).toBe("application/json");
    expect(jsonInit?.body).toBe('{"a":1}');

    const form = new FormData();
    form.append("file", new Blob(["x"]), "a.csv");
    await apiRequest("/echo", { method: "POST", body: form });
    const formInit = fetchMock.mock.calls[1]?.[1];
    expect(formInit?.body).toBe(form);
    expect(new Headers(formInit?.headers).get("content-type")).toBeNull();
  });
});
