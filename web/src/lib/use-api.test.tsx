import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { SWRConfig } from "swr";

// Provide a controlled `apiFetch` so we can assert the cache/dedup behaviour
// of `useApiQuery` without touching the real backend.
const mockApiFetch = vi.fn();
vi.mock("@/lib/agent-api", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

import { useApiQuery } from "@/lib/use-api";

function Probe({ label }: { label: string }) {
  const { data } = useApiQuery<{ value: string }>("/llm/providers");
  return <span data-testid={`${label}-data`}>{data ? data.value : "none"}</span>;
}

function ErrorProbe() {
  const { error } = useApiQuery<{ value: string }>("/llm/providers");
  return <span data-testid="err">{error ? error.message : "none"}</span>;
}

const wrapper = (node: React.ReactNode) => (
  <SWRConfig value={{ provider: () => new Map() }}>{node}</SWRConfig>
);

describe("useApiQuery (audit §7.2 — global query cache)", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("fetches once through the shared fetcher", async () => {
    mockApiFetch.mockResolvedValue({ value: "ok" });
    render(wrapper(<Probe label="a" />));

    expect(await screen.findByTestId("a-data")).toHaveTextContent("ok");
    expect(mockApiFetch).toHaveBeenCalledTimes(1);
    expect(mockApiFetch).toHaveBeenCalledWith("/llm/providers");
  });

  it("deduplicates concurrent requests for the same key", async () => {
    mockApiFetch.mockResolvedValue({ value: "ok" });
    render(
      wrapper(
        <>
          <Probe label="a" />
          <Probe label="b" />
        </>,
      ),
    );

    await screen.findByTestId("b-data");
    // Two consumers, identical key → a single underlying fetch (global cache).
    expect(mockApiFetch).toHaveBeenCalledTimes(1);
  });

  it("surfaces fetch errors via the error state", async () => {
    mockApiFetch.mockRejectedValue(new Error("boom"));
    render(wrapper(<ErrorProbe />));

    expect(await screen.findByTestId("err")).toHaveTextContent("boom");
  });
});
