import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Toaster } from "sonner";
import { toast } from "@/lib/toast";

describe("toast", () => {
  it("renders a toast message", async () => {
    render(<Toaster />);
    toast("Saved successfully");
    expect(await screen.findByText("Saved successfully")).toBeInTheDocument();
  });
});
