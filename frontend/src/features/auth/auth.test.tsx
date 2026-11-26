import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  apiError,
  healthyResponse,
  json,
  mockFetch,
  notSignedIn,
  renderRoute,
  renderSignedIn,
  jsonBody,
  requestPath,
  signedInMe,
} from "@/test/utils";

function callsTo(fetchMock: ReturnType<typeof mockFetch>, path: string) {
  return fetchMock.mock.calls.filter(([input]) => requestPath(input) === path);
}

describe("sign-in guard", () => {
  it("sends anonymous visitors to sign-in and back to where they were going", async () => {
    let signedIn = false;
    const fetchMock = mockFetch({
      "/api/v1/auth/me": () => (signedIn ? json(signedInMe) : notSignedIn()),
      "/api/v1/auth/login": () => {
        signedIn = true;
        return json(signedInMe);
      },
      "/api/v1/health": () => json(healthyResponse),
      "/api/v1/dev/sources/adapters": () => json([]),
    });
    renderRoute("/imports");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Email"), "priya@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Imports" })).toBeInTheDocument();
    const [, init] = callsTo(fetchMock, "/api/v1/auth/login")[0] ?? [];
    expect(jsonBody(init)).toEqual({
      email: "priya@example.test",
      password: "correct horse battery",
    });
    expect(init?.credentials).toBe("include");
  });

  it("says why sign-in failed, with the server's reference", async () => {
    mockFetch({
      "/api/v1/auth/me": notSignedIn,
      "/api/v1/auth/login": () =>
        apiError(401, "invalid_credentials", "The email or password is not correct."),
    });
    renderRoute("/sign-in");
    await userEvent.type(await screen.findByLabelText("Email"), "priya@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "wrong password!!");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Sign-in failed")).toBeInTheDocument();
    expect(screen.getByText("The email or password is not correct.")).toBeInTheDocument();
    expect(screen.getByText(/Reference: 01TESTREQUEST/)).toBeInTheDocument();
  });

  it("explains throttling with the time to wait (A-08)", async () => {
    mockFetch({
      "/api/v1/auth/me": notSignedIn,
      "/api/v1/auth/login": () =>
        apiError(429, "too_many_attempts", "Too many failed sign-in attempts. Try again later.", [
          { field: "retry_after_s", issue: "130" },
        ]),
    });
    renderRoute("/sign-in");
    await userEvent.type(await screen.findByLabelText("Email"), "priya@example.test");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Too many attempts")).toBeInTheDocument();
    expect(screen.getByText(/try again in 3 minutes/)).toBeInTheDocument();
  });

  it("signs out and returns to sign-in", async () => {
    let signedIn = true;
    const fetchMock = mockFetch({
      "/api/v1/auth/me": () => (signedIn ? json(signedInMe) : notSignedIn()),
      "/api/v1/auth/logout": () => {
        signedIn = false;
        return new Response(null, { status: 204 });
      },
      "/api/v1/health": () => json(healthyResponse),
    });
    await renderSignedIn("/");
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    const [, init] = callsTo(fetchMock, "/api/v1/auth/logout")[0] ?? [];
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("csrf-test-token");
  });

  it("never shows internal project labels on public pages", async () => {
    mockFetch({ "/api/v1/auth/me": notSignedIn });
    renderRoute("/register");
    await screen.findByRole("heading", { name: "Create your account" });
    for (const internal of ["Group 2", "Z-5-1", "Batch", "development build", "Milestone"]) {
      expect(document.body.textContent).not.toContain(internal);
    }
  });
});

describe("registration", () => {
  async function fill(password: string) {
    await userEvent.type(await screen.findByLabelText("Email"), "new@example.test");
    await userEvent.type(screen.getByLabelText("Password"), password);
  }

  it("keeps the button disabled until the password is long enough", async () => {
    mockFetch({ "/api/v1/auth/me": notSignedIn });
    renderRoute("/register");
    await fill("short one");
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    expect(screen.getByText(/At least 12 characters/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Password"), " plus more");
    expect(screen.getByRole("button", { name: "Create account" })).toBeEnabled();
  });

  it("shows the server's password rule next to the field", async () => {
    mockFetch({
      "/api/v1/auth/me": notSignedIn,
      "/api/v1/auth/register": () =>
        apiError(422, "validation_failed", "The password is too common.", [
          { field: "password", issue: "is too common; choose a less predictable password" },
        ]),
    });
    renderRoute("/register");
    await fill("Password1234");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(
      await screen.findByText("The password is too common; choose a less predictable password."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute("aria-invalid", "true");
  });

  it("says when the email is already registered", async () => {
    mockFetch({
      "/api/v1/auth/me": notSignedIn,
      "/api/v1/auth/register": () =>
        apiError(409, "email_taken", "An account with this email already exists."),
    });
    renderRoute("/register");
    await fill("correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Email already registered")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    });
  });
});
