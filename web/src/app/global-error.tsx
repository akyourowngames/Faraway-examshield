"use client";

import { ErrorFallback } from "@/components/ErrorFallback";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-black text-white">
        <ErrorFallback
          title="Critical error"
          message={error.message || "An unexpected error occurred."}
          onRetry={reset}
        />
      </body>
    </html>
  );
}
