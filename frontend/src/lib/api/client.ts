/**
 * Minimal typed HTTP client for the FastAPI backend (/api/v1).
 *
 * - Every non-2xx response is parsed as the backend error envelope
 *   `{ error: { code, message, details, request_id } }` (D09 section 2) and thrown as ApiError.
 * - Credentials are sent so the session cookie works once authentication exists; unsafe
 *   methods will add the X-CSRF-Token header at that point (D09 section 1).
 * - Requests time out (default 15 s) and can be cancelled through an AbortSignal.
 */
import { env } from "@/lib/env";

export const API_PREFIX = "/api/v1";

export interface ErrorDetail {
  field: string;
  issue: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetail[];
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: ErrorDetail[] = [],
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string; details?: ErrorDetail[]; request_id?: string | null };
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const { error } = value;
  return typeof error === "object" && error !== null && "code" in error && "message" in error;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: BodyInit | object;
  signal?: AbortSignal;
  timeoutMs?: number;
  /** Treat these non-2xx statuses as a normal response (for example 503 from /health). */
  acceptStatuses?: readonly number[];
}

export function apiUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${env.apiBaseUrl}${API_PREFIX}${clean}`;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = 15_000, acceptStatuses = [] } = options;
  const headers = new Headers({ Accept: "application/json" });
  let payload: BodyInit | undefined;
  if (body instanceof FormData || typeof body === "string" || body instanceof Blob) {
    payload = body;
  } else if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }

  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers,
      body: payload ?? null,
      credentials: "include",
      signal: combined,
    });
  } catch (cause) {
    if (timeout.aborted) {
      throw new ApiError(0, "timeout", "The server did not respond in time.");
    }
    if (signal?.aborted) throw cause;
    throw new ApiError(0, "network_error", "The server could not be reached.");
  }

  const requestId = response.headers.get("x-request-id");
  const text = await response.text();
  let data: unknown = null;
  if (text !== "") {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = null;
    }
  }

  if (response.ok || acceptStatuses.includes(response.status)) {
    return data as T;
  }
  if (isErrorEnvelope(data)) {
    const { code, message, details, request_id } = data.error;
    throw new ApiError(response.status, code, message, details ?? [], request_id ?? requestId);
  }
  throw new ApiError(
    response.status,
    "unexpected_response",
    `Unexpected response (HTTP ${response.status}).`,
    [],
    requestId,
  );
}
