import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  apiError,
  healthyResponse,
  json,
  mockFetch,
  renderSignedIn,
  requestPath,
  workspaceId,
} from "@/test/utils";

const WS = `/api/v1/workspaces/${workspaceId}`;

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
    eligible: 40,
    embedded: 40,
    embedding_failed: 0,
    classified: 40,
    unclassified: 0,
    themes: 2,
    assigned: 30,
    requests: 1,
    request_records: 10,
    categories: { bug_report: 18, feature_request: 10 },
    steps: [],
  },
  error: null,
};

const status = {
  analysable_records: 40,
  records_since_last_run: 0,
  current_run: run,
  latest_run: run,
};

const weekly = [
  { week: "2026-W40", start: "2026-09-28", n: 3 },
  { week: "2026-W41", start: "2026-10-05", n: 5 },
];

const stats = {
  known_customers: 7,
  unknown_identity_records: 1,
  identity_coverage: 0.875,
  share: 0.2,
  sentiment: { negative: 8 },
  weekly,
  undated: 0,
  trend: "up",
};

const checkout = {
  ...stats,
  id: "theme-1",
  name: "Checkout freezes during payment",
  description: "Customers report checkout freezing when paying.",
  record_count: 8,
  pain_point: true,
  vocal_flag: false,
  categories: { bug_report: 8 },
  evidence: [
    {
      record_id: "7f3c0000-0000-4000-8000-000000000000",
      text: "Checkout spins forever after I tap Pay. Email me at [EMAIL]",
      occurred_at: "2026-10-02T00:00:00Z",
      rating: 1,
      source_type: "review",
      cited: true,
    },
  ],
};

const praise = {
  ...checkout,
  id: "theme-2",
  name: "Fast sync praised",
  description: null,
  record_count: 4,
  pain_point: false,
  trend: "flat",
  sentiment: { positive: 4 },
  categories: { praise: 4 },
  evidence: [],
};

const request = {
  ...stats,
  id: "req-1",
  title: "Add dark mode",
  record_count: 10,
  asks: [
    { ask: "Add dark mode", n: 7 },
    { ask: "Add night mode", n: 3 },
  ],
  low_confidence: 0,
  evidence: [],
};

const insights = {
  run_id: "run-1",
  run_finished_at: "2026-11-27T09:02:00Z",
  filters: { from: null, to: null, source_type: null },
  records_analysed: 40,
  themes: [checkout, praise],
  unassigned: 6,
  pain_points: 1,
  requests: [request],
  source_types: ["review", "ticket"],
  date_range: { from: "2026-10-01", to: "2026-10-27" },
};

describe("insights dashboard (UI-11, UI-06)", () => {
  it("shows pain points, themes, trends, evidence and request groups from the API", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${WS}/analysis`]: () => json(status),
      [`${WS}/insights`]: () => json(insights),
    });
    await renderSignedIn("/");
    expect(await screen.findByRole("heading", { name: "Insights" })).toBeInTheDocument();
    expect(await screen.findByText("Checkout freezes during payment")).toBeInTheDocument();
    expect(screen.getByText("Feedback analysed")).toBeInTheDocument();
    expect(screen.getByText("Pain point")).toBeInTheDocument();
    expect(screen.getAllByText(/1 unknown identity \(88% identified\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rising").length).toBeGreaterThan(0);
    expect(screen.getByText("Steady")).toBeInTheDocument();
    expect(screen.getByText(/Checkout spins forever after I tap Pay/)).toBeInTheDocument();
    expect(screen.getByText(/E-7f3c00 .* cited in the theme name/)).toBeInTheDocument();
    expect(screen.getByText("Unassigned: 6 records fit no theme")).toBeInTheDocument();
    expect(screen.getByText("Add dark mode")).toBeInTheDocument();
    expect(screen.getByText(/Also asked as: “Add night mode” \(3\)/)).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Weekly records for Checkout freezes during payment/ }),
    ).toBeInTheDocument();
  });

  it("sends the filters to the API and says when nothing matches", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${WS}/analysis`]: () => json(status),
      [`${WS}/insights`]: () => json(insights),
    });
    await renderSignedIn("/");
    await screen.findByText("Checkout freezes during payment");
    // Next responses: nothing matches the ticket source.
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const path = requestPath(input);
      if (path === `${WS}/insights`) {
        return Promise.resolve(
          json({
            ...insights,
            records_analysed: 0,
            themes: [],
            requests: [],
            unassigned: 0,
            pain_points: 0,
          }),
        );
      }
      if (path === `${WS}/analysis`) return Promise.resolve(json(status));
      return Promise.resolve(json(healthyResponse));
    });
    await userEvent.selectOptions(screen.getByLabelText("Source"), "ticket");
    await userEvent.click(screen.getByLabelText("Pain points only"));
    expect(await screen.findByText("No feedback matches these filters.")).toBeInTheDocument();
    const urls = fetchMock.mock.calls
      .map(([u]) => (typeof u === "string" ? u : ""))
      .filter((u) => u.includes("/insights?"));
    expect(urls.at(-1)).toContain("source_type=ticket");
    expect(urls.at(-1)).toContain("pain_points_only=true");
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() => {
      expect(screen.getByLabelText("Source")).toHaveValue("");
    });
  });

  it("loads more evidence for a theme on request", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${WS}/analysis`]: () => json(status),
      [`${WS}/insights`]: () => json(insights),
      [`${WS}/themes/theme-1`]: () =>
        json({
          ...checkout,
          evidence: [
            ...checkout.evidence,
            {
              ...checkout.evidence[0],
              record_id: "81d20000-0000-4000-8000-000000000000",
              text: "Payment page hangs",
              cited: false,
            },
          ],
        }),
    });
    await renderSignedIn("/");
    const card = (await screen.findByText("Checkout freezes during payment")).closest("li");
    expect(card).not.toBeNull();
    await userEvent.click(
      within(card as HTMLElement).getByRole("button", { name: "Show more evidence" }),
    );
    expect(await screen.findByText(/Payment page hangs/)).toBeInTheDocument();
    expect(screen.getByText("Records per week")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => requestPath(u) === `${WS}/themes/theme-1`)).toBe(
      true,
    );
  });

  it("shows the server's error with its reference", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${WS}/analysis`]: () => json(status),
      [`${WS}/insights`]: () =>
        apiError(503, "database_unavailable", "The database is not reachable."),
    });
    await renderSignedIn("/");
    expect(await screen.findByText("Insights could not load")).toBeInTheDocument();
    expect(screen.getByText("The database is not reachable.")).toBeInTheDocument();
  });

  it("keeps the welcome and setup steps until an analysis has succeeded", async () => {
    mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`${WS}/analysis`]: () =>
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
    expect(screen.getByRole("heading", { name: /Welcome to/ })).toBeInTheDocument();
    expect(screen.queryByText("Feedback analysed")).toBeNull();
  });
});
