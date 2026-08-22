import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import LoginPage from "@/app/login/page";

describe("LoginPage", () => {
  it("renders the sign-in heading and supporting copy", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
    expect(screen.getByText(/sign in to your account to continue/i)).toBeInTheDocument();
  });

  it("renders email and password fields", () => {
    render(<LoginPage />);

    expect(screen.getByPlaceholderText("name@example.com")).toHaveAttribute("type", "email");
    expect(screen.getByPlaceholderText("••••••••")).toHaveAttribute("type", "password");
  });

  it("renders credential and OAuth submit buttons", () => {
    render(<LoginPage />);

    expect(screen.getByRole("button", { name: /sign in/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /google/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /github/i })).toBeInTheDocument();
  });

  it("links to the signup page for new users", () => {
    render(<LoginPage />);

    const signupLink = screen.getByRole("link", { name: /sign up/i });
    expect(signupLink).toHaveAttribute("href", "/signup");
  });
});
