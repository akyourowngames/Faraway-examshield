import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErrorFallback } from "@/components/ErrorFallback";

describe("ErrorFallback", () => {
  it("renders the message inside an alert role", () => {
    render(<ErrorFallback message="Boom" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Boom")).toBeInTheDocument();
  });

  it("shows a retry button only when onRetry is provided", () => {
    const { rerender } = render(<ErrorFallback message="x" />);
    expect(
      screen.queryByRole("button", { name: /try again/i }),
    ).not.toBeInTheDocument();
    rerender(<ErrorFallback message="x" onRetry={() => {}} />);
    expect(
      screen.getByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
  });

  it("calls onRetry when clicked", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(<ErrorFallback message="x" onRetry={onRetry} />);
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
