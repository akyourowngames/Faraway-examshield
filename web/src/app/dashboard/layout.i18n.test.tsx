import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider, useI18n } from "@/lib/i18n";

// A tiny mirror of the nav-label lookup used by the real layout.
const NAV_KEYS = [
  "commandCenter", "examshieldAi", "evidenceCenter", "questionRegistry",
  "threatIntelligence", "investigation", "examLifecycle", "alerts",
  "communityAgents", "settings",
] as const;

function NavProbe() {
  const { t } = useI18n();
  return (
    <nav>
      {NAV_KEYS.map((k) => (
        <span key={k}>{t(`nav.${k}`)}</span>
      ))}
    </nav>
  );
}

function LocaleSwitch() {
  const { setLocale } = useI18n();
  return (
    <button onClick={() => setLocale("hi")}>hi</button>
  );
}

describe("dashboard nav i18n", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it("translates nav labels to Hindi after switching", async () => {
    const user = userEvent.setup();
    render(
      <I18nProvider>
        <NavProbe />
        <LocaleSwitch />
      </I18nProvider>,
    );
    expect(screen.getByText("Command Center")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "hi" }));
    expect(screen.getByText("कमांड सेंटर")).toBeInTheDocument();
    expect(screen.queryByText("Command Center")).not.toBeInTheDocument();
    cleanup();
  });
});
