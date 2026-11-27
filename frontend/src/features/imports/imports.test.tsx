import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  healthyResponse,
  json,
  mockFetch,
  renderSignedIn,
  requestPath,
  signedInMe,
  workspaceId,
} from "@/test/utils";

const IMPORTS = `/api/v1/workspaces/${workspaceId}/imports`;

const finished = {
  id: "import-1",
  source_type: "review",
  status: "completed_with_errors",
  original_filename: "reviews.csv",
  source_file_id: "file-1",
  submitted_by: signedInMe.user.id,
  created_at: "2026-11-27T09:00:00Z",
  started_at: "2026-11-27T09:00:01Z",
  finished_at: "2026-11-27T09:00:04Z",
  job_id: "job-1",
  progress: { processed: 4, total: 4 },
  error: null,
  report: {
    received: 4,
    imported: 2,
    rejected: 1,
    duplicates: 1,
    filtered: { noise: 0, pii_failed: 0 },
    failed: 0,
    reconciled: true,
    flags: { occurred_at_unparseable: 1 },
    pii_masked: { EMAIL: 2 },
    date_range: { from: "2026-10-02T00:00:00Z", to: "2026-10-09T00:00:00Z" },
    not_checked: ["language", "spam"],
  },
};

const rowErrors = {
  items: [
    {
      id: "e1",
      row_number: 3,
      kind: "rejected",
      stage: "validation",
      field: "text",
      code: "text_missing",
      message: "Text is empty.",
    },
  ],
  next_cursor: null,
};

describe("import report (UI-04)", () => {
  it("shows the reconciliation, masked personal data and the rejected rows", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${IMPORTS}/import-1`]: () => json(finished),
      [`${IMPORTS}/import-1/errors`]: () => json(rowErrors),
    });
    await renderSignedIn("/imports/import-1");
    expect(await screen.findByRole("heading", { name: "reviews.csv" })).toBeInTheDocument();
    expect(screen.getByText("Completed with errors")).toBeInTheDocument();
    expect(screen.getByText("Every row is accounted for")).toBeInTheDocument();
    expect(
      screen.getByText(
        "4 received = 2 imported + 1 rejected + 1 duplicates + 0 filtered + 0 failed",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Email addresses: 2")).toBeInTheDocument();
    expect(screen.getByText("Date couldn't be read: 1")).toBeInTheDocument();
    expect(screen.getByText(/Not checked in this version: language and spam/)).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Empty feedback text")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Kind"), "failed");
    const filtered = fetchMock.mock.calls.filter(([u]) => requestPath(u).endsWith("/errors"));
    const last = filtered.at(-1)?.[0];
    expect(typeof last === "string" ? last : "").toContain("kind=failed");
  });

  it("shows progress while the import runs", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${IMPORTS}/import-1`]: () =>
        json({
          ...finished,
          status: "processing",
          report: null,
          progress: { processed: 500, total: 2000 },
        }),
    });
    await renderSignedIn("/imports/import-1");
    expect(await screen.findByText("500 of 2,000 rows")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");
  });

  it("explains a failed import", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${IMPORTS}/import-1`]: () =>
        json({
          ...finished,
          status: "failed",
          error: "Reconciliation error: the counts do not add up to the rows received.",
          report: { ...finished.report, reconciled: false },
        }),
      [`${IMPORTS}/import-1/errors`]: () => json({ items: [], next_cursor: null }),
    });
    await renderSignedIn("/imports/import-1");
    expect(await screen.findByText("The import failed")).toBeInTheDocument();
    expect(screen.getByText(/Reconciliation error/)).toBeInTheDocument();
    expect(screen.getByText("Counts do not add up")).toBeInTheDocument();
    expect(await screen.findByText("No rejected or failed rows")).toBeInTheDocument();
  });
});

describe("imports page roles and history", () => {
  it("shows Viewers the history only", async () => {
    mockFetch({
      "/api/v1/auth/me": () =>
        json({
          ...signedInMe,
          memberships: [
            { workspace_id: workspaceId, workspace_name: "Checkout app", role: "viewer" },
          ],
        }),
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json([]),
      [IMPORTS]: () => json({ items: [finished], next_cursor: null }),
    });
    await renderSignedIn("/imports");
    expect(await screen.findByText("Viewing only")).toBeInTheDocument();
    expect(screen.queryByLabelText(/choose a file/i)).toBeNull();
    const link = await screen.findByRole("link", { name: "reviews.csv" });
    expect(link).toHaveAttribute("href", "/imports/import-1");
    expect(screen.getByText("Completed with errors")).toBeInTheDocument();
  });

  it("warns when the same file was imported before (DR-10)", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json([]),
      [IMPORTS]: () => json({ items: [], next_cursor: null }),
      [`/api/v1/workspaces/${workspaceId}/files`]: () =>
        json(
          {
            input: "file",
            original_filename: "copy.csv",
            size_bytes: 20,
            sha256: "ab".repeat(32),
            detected_format: "csv",
            detected_encoding: "utf-8",
            csv_delimiter: ",",
            transcript_mode: null,
            record_count: 1,
            columns: ["review"],
            preview_rows: [["Slow"]],
            total_rows: 1,
            warnings: [],
            source_type: "review",
            required_fields: ["text"],
            suggested_mapping: { text: "review" },
            id: "file-2",
            duplicate_of_file: {
              id: "file-1",
              original_filename: "reviews.csv",
              uploaded_at: "2026-11-26T09:00:00Z",
            },
          },
          201,
        ),
    });
    await renderSignedIn("/imports");
    await userEvent.upload(
      screen.getByLabelText(/choose a file/i),
      new File(["review\nSlow\n"], "copy.csv"),
    );
    expect(await screen.findByText("This file was imported before")).toBeInTheDocument();
    expect(screen.getByText(/same content as reviews.csv/)).toBeInTheDocument();
  });
});
