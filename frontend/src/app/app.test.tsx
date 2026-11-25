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

const noDatabase = {
  ...healthyResponse,
  status: "unavailable",
  checks: {
    ...healthyResponse.checks,
    database: {
      status: "unavailable",
      latency_ms: null,
      detail: "The database is not configured (DATABASE_URL).",
    },
    model_runtime: { status: "unavailable", latency_ms: 3, detail: "model not pulled: qwen3:4b" },
  },
};

describe("application shell", () => {
  it("shows product branding only, never internal project labels", async () => {
    mockFetch({ "/api/v1/health": () => json(noDatabase, 503) });
    renderRoute("/");
    expect(
      await screen.findByRole("heading", { name: "Welcome to Elucis AI" }),
    ).toBeInTheDocument();
    const text = document.body.textContent;
    for (const internal of [
      "Group 2",
      "Z-5-1",
      "Batch",
      "development build",
      "Developer",
      "Milestone",
    ]) {
      expect(text).not.toContain(internal);
    }
  });

  it("lists every D12 section and only links the ones that work", () => {
    mockFetch({ "/api/v1/health": () => json(healthyResponse) });
    renderRoute("/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(within(nav).getByRole("link", { name: "Imports" })).toHaveAttribute("href", "/imports");
    for (const planned of [
      "Themes",
      "Requests",
      "Review",
      "Opportunities",
      "Documents",
      "Roadmap",
      "Assistant",
    ]) {
      expect(within(nav).queryByRole("link", { name: planned })).toBeNull();
      expect(within(nav).getByText(planned)).toHaveAttribute("aria-disabled", "true");
    }
  });

  it("summarises service health and explains why AI is paused", async () => {
    mockFetch({ "/api/v1/health": () => json(noDatabase, 503) });
    renderRoute("/");
    expect(await screen.findByRole("link", { name: "Database not connected" })).toHaveAttribute(
      "href",
      "/settings/system",
    );
    expect(
      screen.getByText(/The qwen3:4b model isn't installed on this machine yet\./, {
        selector: "span",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("0 of 3 complete")).toBeInTheDocument();
  });

  it("says when the server cannot be reached", async () => {
    mockFetch({ "/api/v1/health": () => Promise.reject(new TypeError("Failed to fetch")) });
    renderRoute("/");
    expect(await screen.findByText("Server not reachable")).toBeInTheDocument();
    expect(screen.getByText(/The server isn't responding/)).toBeInTheDocument();
  });

  it("renders a not-found page", () => {
    mockFetch({ "/api/v1/health": () => json(healthyResponse) });
    renderRoute("/does-not-exist");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

describe("redirects", () => {
  it("sends earlier development paths to their product pages", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
    });
    renderRoute("/dev/file-preview");
    expect(await screen.findByRole("heading", { name: "Imports" })).toBeInTheDocument();
  });
});

describe("system status page", () => {
  it("shows database and AI runtime details from the API", async () => {
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
            ollama_version: "0.40.4",
            models: { "qwen3:4b": false, "qwen3-embedding:0.6b": true },
            detail: "model not pulled: qwen3:4b",
          },
          503,
        ),
    });
    renderRoute("/settings/system");
    expect(await screen.findByText("18.7")).toBeInTheDocument();
    expect(screen.getByText("pgvector 0.8.7")).toBeInTheDocument();
    expect(await screen.findByText("Not installed")).toBeInTheDocument();
    expect(screen.getByText("Installed")).toBeInTheDocument();
  });
});

describe("imports page", () => {
  const preview = {
    input: "file",
    original_filename: "reviews.csv",
    size_bytes: 150,
    sha256: "ab".repeat(32),
    detected_format: "csv",
    detected_encoding: "utf-8",
    csv_delimiter: ",",
    transcript_mode: null,
    record_count: 2,
    columns: ["id", "review", "user"],
    preview_rows: [
      ["1", "App crashes", "u-1"],
      ["2", "", "u-2"],
    ],
    total_rows: 2,
    warnings: ["1 row(s) have fewer values than the header; missing values are empty."],
    source_type: "review",
    required_fields: ["text"],
    suggested_mapping: { text: "review", source_record_id: "id" },
  };
  const report = {
    file: { ...preview },
    source_type: "review",
    column_mapping: { text: "review", source_record_id: "id", customer_id: "user" },
    date_order: null,
    summary: {
      received: 2,
      valid: 1,
      rejected: 1,
      rejected_by_code: { text_missing: 1 },
      flags_by_code: { occurred_at_missing: 1 },
      reconciled: true,
    },
    errors: [
      {
        row_number: 2,
        segment_index: 0,
        field: "text",
        code: "text_missing",
        message: "Text is empty.",
      },
    ],
    errors_truncated: false,
    sample_records: [
      {
        row_number: 1,
        segment_index: 0,
        source_type: "review",
        raw_text: "App crashes",
        text_truncated: false,
        source_record_id: "1",
        occurred_at: null,
        occurred_at_raw: null,
        occurred_at_missing: true,
        customer_ref: "u-1",
        rating_raw: null,
        rating_value: null,
        rating_out_of: null,
        product_version_raw: null,
        speaker: null,
        metadata: {},
        flags: ["occurred_at_missing"],
      },
    ],
    sample_metrics: [],
    warnings: [],
  };

  it("previews a file, suggests column matches and validates every row", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(noDatabase, 503),
      "/api/v1/dev/sources/adapters": () => json(adapters),
      "/api/v1/dev/sources/preview": () => json(preview),
      "/api/v1/dev/sources/validate": () => json(report),
    });
    renderRoute("/imports");
    expect(await screen.findByText("Zendesk tickets")).toBeInTheDocument();
    expect(
      await screen.findByText("Importing starts once the database is connected"),
    ).toBeInTheDocument();

    await userEvent.upload(
      screen.getByLabelText(/choose a file/i),
      new File(["id,review\n1,App crashes\n"], "reviews.csv", { type: "text/csv" }),
    );
    expect(await screen.findByRole("columnheader", { name: "review" })).toBeInTheDocument();
    expect(screen.getByText("Comma")).toBeInTheDocument();
    expect(screen.getByText(/fewer values than the header/)).toBeInTheDocument();

    // Suggested matches are pre-filled but editable; no customer column -> identity warning.
    expect(screen.getByLabelText(/Feedback text/)).toHaveValue("review");
    expect(screen.getByLabelText(/Record ID/)).toHaveValue("id");
    expect(screen.getByText(/customer identity will be unknown/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(/Customer ID/), "user");
    expect(screen.queryByText(/customer identity will be unknown/)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Check records" }));
    expect(await screen.findByText("Records checked")).toBeInTheDocument();
    expect(screen.getByText("Ready to import")).toBeInTheDocument();
    expect(screen.getByText("Empty feedback text")).toBeInTheDocument();
    expect(screen.getByText("Text is empty.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start import" })).toBeDisabled();

    const call = fetchMock.mock.calls.find(([u]) =>
      requestPath(u).endsWith("/dev/sources/validate"),
    );
    const body = call?.[1]?.body as FormData;
    expect(body.get("source_type")).toBe("review");
    expect(JSON.parse(body.get("mapping") as string)).toEqual({
      text: "review",
      source_record_id: "id",
      customer_id: "user",
    });
  });

  it("blocks checking until required fields are matched", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
      "/api/v1/dev/sources/preview": () => json({ ...preview, suggested_mapping: {} }),
    });
    renderRoute("/imports");
    await userEvent.upload(screen.getByLabelText(/choose a file/i), new File(["x"], "r.csv"));
    expect(
      await screen.findByText(/Choose a column for Feedback text to continue/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check records" })).toBeDisabled();
  });

  it("previews pasted text", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
      "/api/v1/dev/sources/preview": () =>
        json({
          ...preview,
          input: "pasted_text",
          original_filename: "pasted-text.txt",
          detected_format: "txt",
          csv_delimiter: null,
          transcript_mode: "paragraphs",
          columns: ["segment_index", "text"],
          preview_rows: [["0", "Export is slow"]],
          total_rows: 1,
          warnings: [],
          suggested_mapping: { text: "text" },
        }),
    });
    renderRoute("/imports");
    await userEvent.click(screen.getByRole("radio", { name: "Paste text" }));
    await userEvent.type(screen.getByLabelText("Pasted feedback"), "Export is slow");
    await userEvent.click(screen.getByRole("button", { name: "Preview text" }));
    expect(await screen.findByText("Pasted text")).toBeInTheDocument();
    expect(screen.getByText(/Text is split automatically/)).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) =>
      requestPath(u).endsWith("/dev/sources/preview"),
    );
    expect((call?.[1]?.body as FormData).get("pasted_text")).toBe("Export is slow");
  });

  it("shows the server's reason and a reference when a file is rejected", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
      "/api/v1/dev/sources/preview": () =>
        json(
          {
            error: {
              code: "validation_failed",
              message: "The file is not valid JSON (line 1, column 2).",
              details: [],
              request_id: "01REQ",
            },
          },
          422,
        ),
    });
    renderRoute("/imports");
    await userEvent.upload(
      screen.getByLabelText(/choose a file/i),
      new File(["{"], "bad.json", { type: "application/json" }),
    );
    expect(
      await screen.findByText("The file is not valid JSON (line 1, column 2)."),
    ).toBeInTheDocument();
    expect(screen.getByText("Reference: 01REQ")).toBeInTheDocument();
  });

  it("rejects unsupported and oversized files before uploading", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json(adapters),
    });
    renderRoute("/imports");
    const big = new File(["x"], "big.csv", { type: "text/csv" });
    Object.defineProperty(big, "size", { value: 21 * 1024 * 1024 });
    await userEvent.upload(screen.getByLabelText(/choose a file/i), big);
    await waitFor(() => {
      expect(screen.getByText(/Files can be up to 20 MB/)).toBeInTheDocument();
    });
    await userEvent.upload(screen.getByLabelText(/choose a file/i), new File(["x"], "sheet.xlsx"), {
      applyAccept: false,
    });
    expect(await screen.findByText(/isn't a CSV, JSON or text file/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => requestPath(u).endsWith("/preview"))).toBe(false);
  });
});
