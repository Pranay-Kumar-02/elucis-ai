import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  apiError,
  healthyResponse,
  json,
  mockFetch,
  renderSignedIn,
  requestPath,
  signedInMe,
  workspaceId,
} from "@/test/utils";

const STATUS = `/api/v1/workspaces/${workspaceId}/analysis`;
const RUNS = `/api/v1/workspaces/${workspaceId}/analysis-runs`;

const run = {
  id: "run-1",
  status: "succeeded",
  is_current: true,
  created_at: "2026-11-27T09:00:00Z",
  started_at: "2026-11-27T09:00:01Z",
  finished_at: "2026-11-27T09:02:00Z",
  job_id: "job-1",
  step: null,
  progress: null,
  config: {},
  report: {
    eligible: 120,
    embedded: 118,
    embedding_failed: 2,
    classified: 116,
    unclassified: 2,
    themes: 7,
    assigned: 101,
    requests: 5,
    request_records: 40,
    categories: { bug_report: 60, feature_request: 40, praise: 16 },
    steps: ["embed", "classify", "cluster", "stats", "name"],
  },
  error: null,
};

describe("analysis panel (UI-05)", () => {
  it("asks for data first when nothing is analysable", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [STATUS]: () =>
        json({
          analysable_records: 0,
          records_since_last_run: 0,
          current_run: null,
          latest_run: null,
        }),
    });
    await renderSignedIn("/");
    expect(
      await screen.findByText("No analysable records; import data first."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run analysis" })).toBeNull();
  });

  it("starts a run with an idempotency key and shows its progress", async () => {
    let started = false;
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [STATUS]: () =>
        json({
          analysable_records: 120,
          records_since_last_run: started ? 0 : 120,
          current_run: null,
          latest_run: started
            ? {
                ...run,
                status: "running",
                is_current: false,
                step: "embed",
                progress: { step: "embed", embedded: 64 },
                report: null,
                finished_at: null,
              }
            : null,
        }),
      [RUNS]: () => {
        started = true;
        return json({ job_id: "job-1", resource_id: "run-1", status: "queued" }, 202);
      },
    });
    await renderSignedIn("/");
    expect(
      await screen.findByText(/120 analysable records · 120 added since the last run/),
    ).toBeInTheDocument();
    expect(screen.getByText("No analysis has run yet in this workspace.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run analysis" }));
    expect(
      await screen.findByText("Reading the meaning of each record (64 done)"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analysis running…" })).toBeDisabled();
    const post = fetchMock.mock.calls.find(
      ([u, init]) => requestPath(u) === RUNS && init?.method === "POST",
    );
    expect(new Headers(post?.[1]?.headers).get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("shows the last run's results and keeps them when a new run fails", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [STATUS]: () =>
        json({
          analysable_records: 120,
          records_since_last_run: 5,
          current_run: run,
          latest_run: {
            ...run,
            id: "run-2",
            status: "failed",
            is_current: false,
            error: "The analysis stopped: ModelUnavailableError.",
          },
        }),
    });
    await renderSignedIn("/");
    expect(await screen.findByText("The last run failed")).toBeInTheDocument();
    expect(screen.getByText(/Previous results are still shown/)).toBeInTheDocument();
    expect(screen.getByText("118")).toBeInTheDocument();
    expect(screen.getByText("Could not be read")).toBeInTheDocument();
    expect(screen.getByText("Themes found")).toBeInTheDocument();
    expect(screen.getByText("Request groups")).toBeInTheDocument();
    expect(screen.getByText("Not labelled")).toBeInTheDocument();
    expect(screen.getByText("Feedback by type")).toBeInTheDocument();
    expect(screen.getByText(/Bug reports/)).toBeInTheDocument();
  });

  it("explains a refused start (model runtime down)", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [STATUS]: () =>
        json({
          analysable_records: 3,
          records_since_last_run: 3,
          current_run: null,
          latest_run: null,
        }),
      [RUNS]: () =>
        apiError(
          503,
          "model_unavailable",
          "The model qwen3-embedding:0.6b is not available in Ollama.",
        ),
    });
    await renderSignedIn("/");
    await userEvent.click(await screen.findByRole("button", { name: "Run analysis" }));
    expect(await screen.findByText("The run could not start")).toBeInTheDocument();
    expect(screen.getByText(/is not available in Ollama/)).toBeInTheDocument();
  });

  it("hides the run button from Viewers", async () => {
    mockFetch({
      "/api/v1/auth/me": () =>
        json({
          ...signedInMe,
          memberships: [
            { workspace_id: workspaceId, workspace_name: "Checkout app", role: "viewer" },
          ],
        }),
      "/api/v1/health": () => json(healthyResponse),
      [STATUS]: () =>
        json({
          analysable_records: 3,
          records_since_last_run: 3,
          current_run: null,
          latest_run: null,
        }),
    });
    await renderSignedIn("/");
    expect(await screen.findByText(/3 analysable records/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run analysis" })).toBeNull();
  });
});
