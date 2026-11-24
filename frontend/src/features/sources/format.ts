export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const ACCEPTED_EXTENSIONS = [".csv", ".json", ".txt"];
export const ACCEPTED_FILES = ACCEPTED_EXTENSIONS.join(",");
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // A-06; the server enforces it too
