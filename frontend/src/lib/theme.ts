/** Light / dark / system theme, remembered per browser. */
export type ThemeChoice = "system" | "light" | "dark";

const STORAGE_KEY = "pmc.theme";
const media = () => window.matchMedia("(prefers-color-scheme: dark)");

export function readTheme(): ThemeChoice {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const dark = choice === "dark" || (choice === "system" && media().matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
}

export function saveTheme(choice: ThemeChoice): void {
  try {
    if (choice === "system") window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // Storage can be unavailable (private mode); the choice then lasts for this page only.
  }
  applyTheme(choice);
}

/** Apply the saved theme now and follow OS changes while the choice is "system". */
export function initTheme(): void {
  applyTheme(readTheme());
  media().addEventListener("change", () => {
    if (readTheme() === "system") applyTheme("system");
  });
}
