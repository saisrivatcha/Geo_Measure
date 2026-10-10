/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8")) as {
  version: string;
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // In development /api is proxied to the FastAPI backend, so the browser talks to
  // one origin and CORS is not involved. VITE_API_BASE_URL can still point the
  // client at another host explicitly.
  const proxyTarget = env.VITE_PROXY_TARGET ?? "http://localhost:8000";

  return {
    plugins: [react()],
    define: { __APP_VERSION__: JSON.stringify(pkg.version) },
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    server: {
      port: 5173,
      proxy: { "/api": { target: proxyTarget, changeOrigin: true } },
    },
    preview: {
      port: 4173,
      proxy: { "/api": { target: proxyTarget, changeOrigin: true } },
    },
    build: {
      sourcemap: true,
      rollupOptions: {
        output: {
          manualChunks: {
            react: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"],
            map: ["leaflet", "react-leaflet"],
          },
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: { modules: { classNameStrategy: "non-scoped" } },
      restoreMocks: true,
      // Absolute API origin in tests: Node's fetch cannot resolve relative URLs.
      env: { VITE_API_BASE_URL: "http://api.test" },
    },
  };
});
