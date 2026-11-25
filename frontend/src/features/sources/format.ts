export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const ACCEPTED_EXTENSIONS = [".csv", ".json", ".txt"];
export const ACCEPTED_FILES = ACCEPTED_EXTENSIONS.join(",");
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // A-06; the server enforces it too

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
// Date-only values are stored as 00:00 UTC; show them as that calendar date, not a local time.
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" });

/** Times show in the browser's time zone (A-23); values given without a time stay dates. */
export function formatOccurredAt(iso: string, raw: string | null): string {
  const hasTime = raw !== null && /\d:\d{2}/.test(raw);
  return (hasTime ? dateTime : dateOnly).format(new Date(iso));
}
