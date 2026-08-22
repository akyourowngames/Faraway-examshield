import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // React 19's production build has no `React.act` export, but
    // @testing-library/react depends on it. Force the conventional test env so
    // Vitest loads the development React build even when the shell has a global
    // NODE_ENV=production (e.g. Windows CI/dev machines).
    env: {
      NODE_ENV: "test",
      NEXT_PUBLIC_SUPABASE_URL: "https://placeholder.supabase.co",
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "placeholder-anon-key-for-tests",
    },
  },
});
