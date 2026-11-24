/**
 * Typed, validated access to build-time environment variables.
 * Only VITE_* variables are exposed to the browser, so nothing here may be secret.
 */
function normaliseBaseUrl(raw: string | undefined): string {
  const value = (raw ?? "").trim();
  if (value === "") return "";
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`VITE_API_BASE_URL must be an absolute URL, got "${value}"`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("VITE_API_BASE_URL must use http or https");
  }
  return value.replace(/\/+$/, "");
}

export const env = {
  apiBaseUrl: normaliseBaseUrl(import.meta.env.VITE_API_BASE_URL),
  mode: import.meta.env.MODE,
  isDev: import.meta.env.DEV,
} as const;

export { normaliseBaseUrl };
