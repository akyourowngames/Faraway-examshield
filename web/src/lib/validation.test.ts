import { describe, it, expect } from "vitest";
import {
  loginSchema,
  signupSchema,
  agentBasicsSchema,
  agentLlmSchema,
  AGENT_CATEGORIES,
  firstError,
  fieldErrors,
} from "@/lib/validation";

describe("loginSchema", () => {
  it("accepts a valid email and password", () => {
    expect(loginSchema.safeParse({ email: "student@example.com", password: "secret123" }).success).toBe(true);
  });

  it("rejects a malformed email", () => {
    const result = loginSchema.safeParse({ email: "not-an-email", password: "secret123" });
    expect(result.success).toBe(false);
    expect(firstError(result)).toMatch(/email/i);
  });

  it("rejects an empty password (preserves prior required-check behaviour)", () => {
    const result = loginSchema.safeParse({ email: "student@example.com", password: "" });
    expect(result.success).toBe(false);
    expect(firstError(result)).toMatch(/password/i);
  });
});

describe("signupSchema", () => {
  it("accepts a valid signup payload", () => {
    const result = signupSchema.safeParse({ name: "Jane Doe", email: "jane@example.com", password: "supersecret" });
    expect(result.success).toBe(true);
  });

  it("requires a name", () => {
    const result = signupSchema.safeParse({ name: "   ", email: "jane@example.com", password: "supersecret" });
    expect(result.success).toBe(false);
    expect(fieldErrors(result).name).toBeDefined();
  });

  it("requires an email-shaped value", () => {
    const result = signupSchema.safeParse({ name: "Jane", email: "jane", password: "supersecret" });
    expect(result.success).toBe(false);
    expect(fieldErrors(result).email).toBeDefined();
  });

  it("requires a password of at least 8 characters", () => {
    const result = signupSchema.safeParse({ name: "Jane", email: "jane@example.com", password: "short" });
    expect(result.success).toBe(false);
    expect(fieldErrors(result).password).toMatch(/8 characters/);
  });

  it("maps each failing field independently", () => {
    const result = signupSchema.safeParse({ name: "", email: "bad", password: "x" });
    expect(result.success).toBe(false);
    const errors = fieldErrors(result);
    expect(errors.name).toBeDefined();
    expect(errors.email).toBeDefined();
    expect(errors.password).toBeDefined();
  });
});

describe("agentBasicsSchema", () => {
  it("accepts a complete basics payload", () => {
    const result = agentBasicsSchema.safeParse({
      name: "School Assistant",
      description: "Helps students",
      category: "education",
      visibility: "private",
    });
    expect(result.success).toBe(true);
  });

  it("requires a name", () => {
    const result = agentBasicsSchema.safeParse({ name: "", category: "general", visibility: "public" });
    expect(result.success).toBe(false);
    expect(firstError(result)).toMatch(/name/i);
  });

  it("rejects an unknown category", () => {
    const result = agentBasicsSchema.safeParse({ name: "X", category: "not-a-category", visibility: "private" });
    expect(result.success).toBe(false);
  });

  it("lists every category the UI offers", () => {
    expect(AGENT_CATEGORIES).toEqual([
      "education",
      "school-assistant",
      "university-assistant",
      "coaching-assistant",
      "security-assistant",
      "general",
    ]);
  });
});

describe("agentLlmSchema", () => {
  it("requires both an api key and a model", () => {
    const result = agentLlmSchema.safeParse({ apiKey: "", model: "" });
    expect(result.success).toBe(false);
    const errors = fieldErrors(result);
    expect(errors.apiKey).toMatch(/API key/i);
    expect(errors.model).toMatch(/model/i);
  });

  it("passes with both present", () => {
    expect(agentLlmSchema.safeParse({ apiKey: "sk-123", model: "gpt-4o" }).success).toBe(true);
  });
});
