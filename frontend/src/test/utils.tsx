import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import { createQueryClient } from "@/app/query-client";
import { routes } from "@/app/routes";

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "x-request-id": "01TESTREQUEST0000000000000",
      ...headers,
    },
  });
}

export function requestPath(input: RequestInfo | URL): string {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  return new URL(url, "http://localhost").pathname;
}

export const workspaceId = "8f6b2a8e-2f63-4d86-9a43-2f0d6f1d0a11";

/** A signed-in Owner with one workspace: the default session in tests. */
export const signedInMe = {
  user: {
    id: "1c1d7f0e-8a6e-4b4f-9d55-6b1b0c7a3f20",
    email: "priya@example.test",
    display_name: "Priya",
    created_at: "2026-11-26T09:00:00Z",
  },
  memberships: [{ workspace_id: workspaceId, workspace_name: "Checkout app", role: "owner" }],
  csrf_token: "csrf-test-token",
};

export function apiError(status: number, code: string, message: string, details: object[] = []) {
  return json(
    { error: { code, message, details, request_id: "01TESTREQUEST0000000000000" } },
    status,
  );
}

export const notSignedIn = () => apiError(401, "not_authenticated", "Sign in to continue.");

/**
 * Replace global fetch with a router of URL-path handlers; unknown paths return 404.
 * ``/api/v1/auth/me`` answers with ``signedInMe`` unless a test overrides it.
 */
export function mockFetch(handlers: Record<string, Handler>) {
  const all: Record<string, Handler> = { "/api/v1/auth/me": () => json(signedInMe), ...handlers };
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = requestPath(input);
    const handler = all[path];
    return handler
      ? handler(path, init)
      : json(
          { error: { code: "not_found", message: "Not found.", details: [], request_id: "x" } },
          404,
        );
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function renderRoute(path: string) {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { retry: false, refetchInterval: false } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

export const healthyResponse = {
  status: "degraded",
  service: "elucis-api",
  version: "0.1.0",
  checks: {
    database: { status: "ok", latency_ms: 2.1, detail: null },
    model_runtime: { status: "unavailable", latency_ms: 3, detail: "not reachable" },
    worker: { status: "not_configured", latency_ms: null, detail: "created in the schema task" },
  },
};

/** Render a page behind sign-in and wait until the session check has let it through. */
export async function renderSignedIn(path: string) {
  const view = renderRoute(path);
  await screen.findByRole("main");
  return view;
}

/** The JSON body a mocked request was sent with. */
export function jsonBody(init: RequestInit | undefined): unknown {
  return typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
}
