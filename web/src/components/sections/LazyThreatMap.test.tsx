import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LazyThreatMap } from "@/components/sections/LazyThreatMap";

describe("LazyThreatMap", () => {
  it("renders a loading fallback while the map chunk loads", () => {
    render(<LazyThreatMap />);
    expect(screen.getByText(/loading threat map/i)).toBeInTheDocument();
  });
});
