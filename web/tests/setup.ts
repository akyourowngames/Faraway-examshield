import "@testing-library/jest-dom/vitest";
import { afterEach, expect, vi } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";
import { cleanup } from "@testing-library/react";

expect.extend(axeMatchers);

// RTL auto-cleanup only hooks in when globals are enabled; do it explicitly.
afterEach(() => {
  cleanup();
});

// Router is provided by Next at runtime; tests only need a stable stub.
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// The real client throws without Supabase env vars; auth calls are stubbed.
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signInWithPassword: vi.fn().mockResolvedValue({ data: null, error: null }),
      signInWithOAuth: vi.fn().mockResolvedValue({ data: null, error: null }),
    },
  }),
}));
