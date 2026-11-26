import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  apiError,
  healthyResponse,
  json,
  mockFetch,
  renderSignedIn,
  jsonBody,
  requestPath,
  signedInMe,
  workspaceId,
} from "@/test/utils";

const workspace = {
  id: workspaceId,
  name: "Checkout app",
  description: "Payments",
  product_name: null,
  product_description: null,
  target_users: null,
  glossary: {},
  role: "owner",
  created_at: "2026-11-26T09:00:00Z",
};

const members = {
  items: [
    {
      user_id: signedInMe.user.id,
      email: signedInMe.user.email,
      display_name: "Priya",
      role: "owner",
      added_at: "2026-11-26T09:00:00Z",
    },
    {
      user_id: "2d2e8f1a-1b2c-4d5e-8f90-a1b2c3d4e5f6",
      email: "arjun@example.test",
      display_name: null,
      role: "viewer",
      added_at: "2026-11-26T10:00:00Z",
    },
  ],
  next_cursor: null,
};

function asRole(role: "owner" | "editor" | "viewer") {
  return {
    ...signedInMe,
    memberships: [{ workspace_id: workspaceId, workspace_name: "Checkout app", role }],
  };
}

describe("workspaces", () => {
  it("guides a new user to create a first workspace, sending the CSRF token", async () => {
    let memberships: unknown[] = [];
    const fetchMock = mockFetch({
      "/api/v1/auth/me": () => json({ ...signedInMe, memberships }),
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/workspaces": (_path, init) => {
        if (init?.method === "POST") {
          memberships = signedInMe.memberships;
          return json(workspace, 201);
        }
        return json({ items: [], next_cursor: null });
      },
    });
    await renderSignedIn("/workspaces");
    expect(await screen.findByText("Create your first workspace")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Name"), "Checkout app");
    await userEvent.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(
      await screen.findByRole("heading", { name: "Welcome to Elucis AI" }),
    ).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(
      ([input, init]) => requestPath(input) === "/api/v1/workspaces" && init?.method === "POST",
    );
    expect(jsonBody(post?.[1])).toEqual({ name: "Checkout app" });
    expect(new Headers(post?.[1]?.headers).get("X-CSRF-Token")).toBe("csrf-test-token");
  });

  it("lets Owners manage members, defaulting new members to Viewer", async () => {
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      [`/api/v1/workspaces/${workspaceId}/members`]: (_path, init) =>
        init?.method === "POST" ? json(members.items[1], 201) : json(members),
    });
    await renderSignedIn("/settings/members");
    expect(await screen.findByText("arjun@example.test")).toBeInTheDocument();
    expect(screen.getByLabelText("Role")).toHaveValue("viewer"); // SEC-21
    expect(screen.getByLabelText("Role of arjun@example.test")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Email"), "new@example.test");
    await userEvent.click(screen.getByRole("button", { name: "Add member" }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
      expect(jsonBody(post?.[1])).toEqual({
        email: "new@example.test",
        role: "viewer",
      });
    });
  });

  it("shows other roles the member list without any controls", async () => {
    mockFetch({
      "/api/v1/auth/me": () => json(asRole("viewer")),
      "/api/v1/health": () => json(healthyResponse),
      [`/api/v1/workspaces/${workspaceId}/members`]: () => json(members),
    });
    await renderSignedIn("/settings/members");
    expect(await screen.findByText("arjun@example.test")).toBeInTheDocument();
    expect(screen.getByText(/Only Owners can add members/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add member" })).toBeNull();
    const table = screen.getByRole("table");
    expect(within(table).queryByRole("combobox")).toBeNull(); // no role selectors
    expect(within(table).getByText("Viewer")).toBeInTheDocument(); // roles shown as text
    expect(within(table).queryByRole("button")).toBeNull(); // no remove buttons
  });

  it("makes settings read-only for non-Owners and hides deletion", async () => {
    mockFetch({
      "/api/v1/auth/me": () => json(asRole("editor")),
      "/api/v1/health": () => json(healthyResponse),
      [`/api/v1/workspaces/${workspaceId}`]: () => json({ ...workspace, role: "editor" }),
    });
    await renderSignedIn("/settings/general");
    expect(await screen.findByText(/Only Owners can change these settings/)).toBeInTheDocument();
    expect(screen.getByLabelText("Workspace name")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    expect(screen.queryByText("Delete workspace")).toBeNull();
  });

  it("deletes only after the exact name is typed, then follows the job to completion", async () => {
    let deleted = false;
    const fetchMock = mockFetch({
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/workspaces": () => json({ items: deleted ? [] : [workspace], next_cursor: null }),
      [`/api/v1/workspaces/${workspaceId}`]: (_path, init) => {
        if (init?.method === "DELETE") {
          deleted = true;
          return json({ job_id: "job-1", resource_id: workspaceId, status: "queued" }, 202);
        }
        return deleted
          ? apiError(404, "not_found", "The resource was not found.")
          : json(workspace);
      },
    });
    await renderSignedIn("/settings/general");
    const confirm = await screen.findByLabelText(/to confirm/);
    const button = screen.getByRole("button", { name: "Delete workspace" });
    expect(button).toBeDisabled();
    await userEvent.type(confirm, "Checkout ap");
    expect(button).toBeDisabled();
    await userEvent.type(confirm, "p");
    expect(button).toBeEnabled();
    await userEvent.click(button);

    expect(await screen.findByText("Workspace deleted", {}, { timeout: 4000 })).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "DELETE");
    expect(jsonBody(call?.[1])).toEqual({ confirm_name: "Checkout app" });
    const headers = new Headers(call?.[1]?.headers);
    expect(headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(headers.get("X-CSRF-Token")).toBe("csrf-test-token");
  });
});
