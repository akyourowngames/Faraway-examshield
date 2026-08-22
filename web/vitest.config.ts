<<<<<<< HEAD
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
=======
import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
>>>>>>> origin/main

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
<<<<<<< HEAD
      "@": fileURLToPath(new URL("./src", import.meta.url)),
=======
      "@": path.resolve(rootDir, "src"),
>>>>>>> origin/main
    },
  },
  test: {
    environment: "jsdom",
<<<<<<< HEAD
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // Placeholder public Supabase values. They are NEXT_PUBLIC_*/anon-only
    // (non-sensitive) and only exist so components that call createClient()
    // during render don't hit the missing-URL path. Real values come from the
    // deployment environment at runtime.
    env: {
      NEXT_PUBLIC_SUPABASE_URL: "https://placeholder.supabase.co",
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "placeholder-anon-key-for-tests",
    },
=======
    setupFiles: ["./tests/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "tests/**/*.test.{ts,tsx}"],
    css: false,
>>>>>>> origin/main
  },
});
