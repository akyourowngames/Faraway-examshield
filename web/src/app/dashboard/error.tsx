"use client";

import { useEffect } from "react";
import { ErrorFallback } from "@/components/ErrorFallback";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <ErrorFallback
      message={error.message || "An unexpected error occurred."}
      onRetry={reset}
    />
  );
}
