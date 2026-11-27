import type { ImportStatus } from "@/lib/api/types";

export const statusLabels: Record<ImportStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  completed_with_errors: "Completed with errors",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const statusVariant: Record<
  ImportStatus,
  "secondary" | "success" | "warning" | "destructive" | "outline"
> = {
  queued: "secondary",
  processing: "secondary",
  completed: "success",
  completed_with_errors: "warning",
  failed: "destructive",
  cancelled: "outline",
};

/** D06 §3.1 outcomes, in pipeline order. */
export const filteredLabels: Record<string, string> = {
  noise: "Noise",
  pii_failed: "Personal data could not be masked",
  non_english: "Not English",
  spam: "Spam",
  spam_review: "Awaiting spam review",
};

export const stageLabels: Record<string, string> = {
  validation: "Validation",
  cleaning: "Cleaning",
  noise: "Noise check",
  standardisation: "Standardisation",
  pii: "Personal data masking",
  language: "Language",
  duplicate: "Duplicates",
  spam: "Spam",
  other: "Other",
};

export const piiLabels: Record<string, string> = {
  EMAIL: "Email addresses",
  PHONE: "Phone numbers",
  CARD: "Card numbers",
  ID: "Government IDs",
  NAME: "Personal names",
};

const when = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const day = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" });

export const formatWhen = (iso: string) => when.format(new Date(iso));
export const formatDay = (iso: string) => day.format(new Date(iso));
