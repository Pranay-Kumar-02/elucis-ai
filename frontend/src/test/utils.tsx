import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
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

/** Replace global fetch with a router of URL-path handlers; unknown paths return 404. */
export function mockFetch(handlers: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = requestPath(input);
    const handler = handlers[path];
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
  service: "copilot-api",
  version: "0.1.0",
  checks: {
    database: { status: "ok", latency_ms: 2.1, detail: null },
    model_runtime: { status: "unavailable", latency_ms: 3, detail: "not reachable" },
    worker: { status: "not_configured", latency_ms: null, detail: "created in the schema task" },
  },
};
