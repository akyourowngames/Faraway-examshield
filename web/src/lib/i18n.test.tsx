import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider, useI18n } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

function Consumer() {
  const { t, setLocale, locale } = useI18n();
  return (
    <div>
      <span data-testid="label">{t("auth.signIn")}</span>
      <span data-testid="locale">{locale}</span>
      <button onClick={() => setLocale("hi")}>switch-hi</button>
    </div>
  );
}

describe("i18n", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it("returns English by default and switches to Hindi, persisting the choice", async () => {
    const user = userEvent.setup();
    render(
      <I18nProvider>
        <Consumer />
        <LanguageSwitcher />
      </I18nProvider>,
    );
    expect(screen.getByTestId("label")).toHaveTextContent("Sign In");

    await user.click(screen.getByRole("button", { name: "switch-hi" }));
    expect(screen.getByTestId("label")).toHaveTextContent("साइन इन");
    expect(screen.getByTestId("locale")).toHaveTextContent("hi");
    expect(window.localStorage.getItem("examshield.locale")).toBe("hi");
  });

  it("renders both language toggle buttons", () => {
    render(
      <I18nProvider>
        <LanguageSwitcher />
      </I18nProvider>,
    );
    expect(screen.getByRole("button", { name: "EN" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "हिंदी" })).toBeInTheDocument();
  });
});
