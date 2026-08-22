import { describe, it, expect, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { FadeIn } from "@/components/Motion";

function mockMatchMedia(matches: boolean) {
  window.matchMedia = ((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}

describe("FadeIn", () => {
  it("renders its children", () => {
    render(<FadeIn>Hello</FadeIn>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("starts hidden (opacity 0) when motion is allowed", () => {
    mockMatchMedia(false);
    const { container } = render(
      <FadeIn data-testid="box">Hello</FadeIn>,
    );
    const el = container.querySelector("[data-testid='box']") as HTMLElement;
    expect(el.style.opacity).toBe("0");
    cleanup();
  });

  it("starts visible (opacity 1) when reduced motion is requested", () => {
    mockMatchMedia(true);
    const { container } = render(
      <FadeIn data-testid="box">Hello</FadeIn>,
    );
    const el = container.querySelector("[data-testid='box']") as HTMLElement;
    expect(el.style.opacity).toBe("1");
    cleanup();
  });
});
