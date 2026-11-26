import { AlertTriangle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ApiError } from "@/lib/api/client";

/**
 * The error state of D12 §4: the API's own message, what to do next, and the request ID
 * for support. Messages never contain internals (D09 §2 guarantees that server-side).
 */
export function ErrorAlert({
  error,
  title = "Something went wrong",
  hint,
}: {
  error: unknown;
  title?: string;
  hint?: string;
}) {
  const apiError = error instanceof ApiError ? error : null;
  const message = apiError?.message ?? "The request could not be completed. Try again.";
  return (
    <Alert variant="destructive">
      <AlertTriangle aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {hint && <p>{hint}</p>}
        {apiError?.requestId && <p className="text-[12px]">Reference: {apiError.requestId}</p>}
      </AlertDescription>
    </Alert>
  );
}
