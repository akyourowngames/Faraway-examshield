import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nProvider } from "@/lib/i18n";
import LoginPage from "@/app/login/page";

function renderPage() {
  return render(
    <I18nProvider>
      <LoginPage />
    </I18nProvider>,
  );
}

describe("LoginPage", () => {
  it("renders the sign-in heading and supporting copy", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
    expect(screen.getByText(/sign in to your account to continue/i)).toBeInTheDocument();
  });

  it("renders email and password fields", () => {
    renderPage();

    expect(screen.getByPlaceholderText("name@example.com")).toHaveAttribute("type", "email");
    expect(screen.getByPlaceholderText("\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022")).toHaveAttribute("type", "password");
  });

  it("renders credential and OAuth submit buttons", () => {
    renderPage();

    expect(screen.getByRole("button", { name: /sign in/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /google/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /github/i })).toBeInTheDocument();
  });

  it("links to the signup page for new users", () => {
    renderPage();

    const signupLink = screen.getByRole("link", { name: /sign up/i });
    expect(signupLink).toHaveAttribute("href", "/signup");
  });
});
