import { z } from "zod";

/**
 * Centralized form-validation schemas (audit §7.1 — "No form validation library").
 *
 * These replace the ad-hoc `if (!x.trim())` checks that were scattered across the
 * auth and agent-builder forms with a single, typed source of truth. Each schema
 * is a pure function, so it is unit-testable without rendering a component
 * (see validation.test.ts).
 */

// ── Auth ──

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

export const signupSchema = z.object({
  name: z.string().trim().min(1, "Full name is required").max(80, "Name is too long"),
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

// ── Agent builder ──

export const AGENT_CATEGORIES = [
  "education",
  "school-assistant",
  "university-assistant",
  "coaching-assistant",
  "security-assistant",
  "general",
] as const;

export const agentBasicsSchema = z.object({
  name: z.string().trim().min(1, "Agent name is required").max(80, "Agent name is too long"),
  description: z.string().max(500, "Description is too long").optional().default(""),
  category: z.enum(AGENT_CATEGORIES),
  visibility: z.enum(["private", "public"]),
});

export const agentLlmSchema = z.object({
  apiKey: z.string().min(1, "API key is required"),
  model: z.string().min(1, "Select a model"),
});

// ── Helpers ──

export type ZodResult = z.ZodSafeParseResult<unknown>;

/** Returns the first validation message, or null when the input is valid. */
export function firstError(result: ZodResult): string | null {
  if (result.success) return null;
  return result.error.issues[0]?.message ?? "Invalid input";
}

/** Maps field paths to their first validation message (e.g. { email: "..." }). */
export function fieldErrors(result: ZodResult): Record<string, string> {
  if (result.success) return {};
  const out: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = String(issue.path[0] ?? "_");
    if (!(key in out)) out[key] = issue.message;
  }
  return out;
}
