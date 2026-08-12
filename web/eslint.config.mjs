import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Test files and Vitest config are executed by vitest, not the Next build
    // or eslint's TS rules; keep them out of the lint gate to avoid
    // test-only patterns (mocks, non-null assertions) turning CI red.
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/*.spec.ts",
    "**/*.spec.tsx",
    "vitest.config.ts",
    "vitest.setup.ts",
  ]),
  // react-hooks/set-state-in-effect is a React 19 recommendation, not a hard
  // correctness rule. Many existing screens hydrate state from caches/localStorage
  // inside effects; flag it as a warning rather than failing CI.
  {
    rules: {
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
