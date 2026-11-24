/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// The dev server proxies /api to FastAPI, so the browser talks to one origin. That keeps
// the session cookie same-site (SameSite=Lax) and avoids CORS in day-to-day development.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_DEV_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy: { "/api": { target: apiTarget, changeOrigin: false } },
    },
    preview: { host: "127.0.0.1", port: 4173, strictPort: true },
    build: { sourcemap: true, target: "es2022" },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: true,
      restoreMocks: true,
      coverage: { provider: "v8", include: ["src/**/*.{ts,tsx}"], exclude: ["src/test/**"] },
    },
  };
});
