import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FileUp } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="No Data" description="Nothing here yet." />);
    expect(screen.getByText("No Data")).toBeInTheDocument();
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
  });

  it("fires the action button", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(
      <EmptyState title="Empty" action={<button onClick={onClick}>Add</button>} />,
    );
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(onClick).toHaveBeenCalled();
  });
});
