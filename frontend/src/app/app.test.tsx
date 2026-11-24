import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { healthyResponse, json, mockFetch, renderRoute, requestPath } from "@/test/utils";

const adapters = [
  {
    kind: "file",
    label: "File upload (CSV, JSON, TXT)",
    status: "implemented",
    formats: ["csv"],
    auth: null,
    requirement: null,
    notes: null,
  },
  {
    kind: "zendesk",
    label: "Zendesk tickets",
    status: "designed",
    formats: [],
    auth: "Bearer token (admin)",
    requirement: null,
    notes: null,
  },
];

describe("application shell", () => {
  it("renders navigation and the dashboard with live health", async () => {
    mockFetch({ "/api/v1/health": () => json(healthyResponse) });
    renderRoute("/");
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "File preview" })).toHaveAttribute(
      "href",
      "/dev/file-preview",
    );
    expect(await screen.findAllByText("Degraded")).not.toHaveLength(0);
    expect(screen.getByText("Database (PostgreSQL + pgvector)")).toBeInTheDocument();
    expect(screen.getByText("Not set up yet")).toBeInTheDocument();
  });

  it("shows when the API is unreachable", async () => {
    mockFetch({ "/api/v1/health": () => Promise.reject(new TypeError("Failed to fetch")) });
    renderRoute("/");
    expect(await screen.findByText(/API is not reachable/)).toBeInTheDocument();
  });

  it("renders a 404 page for unknown routes", () => {
    mockFetch({ "/api/v1/health": () => json(healthyResponse) });
    renderRoute("/does-not-exist");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

describe("system status page", () => {
  it("shows database and model runtime details", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/health/database": () =>
        json({
          status: "ok",
          latency_ms: 2,
          server_version: "18.7",
          pgvector_version: "0.8.7",
          database: "copilot_dev",
          role: "app_api",
          detail: null,
        }),
      "/api/v1/health/model-runtime": () =>
        json(
          {
            status: "unavailable",
            latency_ms: 3,
            ollama_version: null,
            models: null,
            detail: "not reachable",
          },
          503,
        ),
    });
    renderRoute("/system");
    expect(await screen.findByText("18.7")).toBeInTheDocument();
    expect(screen.getByText("0.8.7")).toBeInTheDocument();
    expect(await screen.findByText("not reachable")).toBeInTheDocument();
  });
});

describe("file preview page", () => {
  it("uploads a file and shows the detected preview", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
      "/api/v1/dev/sources/preview": () =>
        json({
          original_filename: "reviews.csv",
          size_bytes: 150,
          sha256: "ab".repeat(32),
          detected_format: "csv",
          detected_encoding: "utf-8",
          csv_delimiter: ",",
          transcript_mode: null,
          columns: ["id", "review"],
          preview_rows: [
            ["1", "App crashes"],
            ["2", "Add dark mode"],
          ],
          total_rows: 2,
          warnings: ["1 row(s) have a different number of values than the header."],
        }),
    });
    renderRoute("/dev/file-preview");
    expect(await screen.findByText("Zendesk tickets")).toBeInTheDocument();
    expect(screen.getByText("Implemented")).toBeInTheDocument();

    const input = screen.getByLabelText(/choose a file/i);
    await userEvent.upload(
      input,
      new File(["id,review\n1,App crashes\n"], "reviews.csv", { type: "text/csv" }),
    );

    expect(await screen.findByText("App crashes")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "review" })).toBeInTheDocument();
    expect(screen.getByText(/different number of values/)).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) =>
      requestPath(u).endsWith("/dev/sources/preview"),
    );
    expect(call?.[1]?.method).toBe("POST");
    expect(call?.[1]?.body).toBeInstanceOf(FormData);
  });

  it("shows the server error message and request ID", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
      "/api/v1/dev/sources/preview": () =>
        json(
          {
            error: {
              code: "unsupported_format",
              message: "Only CSV, JSON and TXT files are supported.",
              details: [],
              request_id: "01REQ",
            },
          },
          415,
        ),
    });
    renderRoute("/dev/file-preview");
    await userEvent.upload(
      screen.getByLabelText(/choose a file/i),
      new File(["x"], "notes.txt", { type: "text/plain" }),
    );
    expect(
      await screen.findByText("Only CSV, JSON and TXT files are supported."),
    ).toBeInTheDocument();
    expect(screen.getByText("Request ID: 01REQ")).toBeInTheDocument();
  });

  it("rejects files over 20 MB before uploading", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
    });
    renderRoute("/dev/file-preview");
    const big = new File(["x"], "big.csv", { type: "text/csv" });
    Object.defineProperty(big, "size", { value: 21 * 1024 * 1024 });
    await userEvent.upload(screen.getByLabelText(/choose a file/i), big);
    await waitFor(() => {
      expect(screen.getByText(/the limit is 20 MB/)).toBeInTheDocument();
    });
    expect(fetchMock.mock.calls.some(([u]) => requestPath(u).endsWith("/preview"))).toBe(false);
  });
});
