import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { axe } from "vitest-axe";
import { SkipLink } from "@/components/SkipLink";

describe("a11y baseline", () => {
  it("has no axe violations for a landmarked page fixture", async () => {
    const { container } = render(
      <div>
        <SkipLink />
        <main id="main-content">
          <h1>Command Center</h1>
          <button type="button">Action</button>
        </main>
      </div>,
    );
    // vitest-axe's matcher type augmentation predates vitest 4's generic
    // Assertion, so assert on the violations array directly.
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
