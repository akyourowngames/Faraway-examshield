"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

export function AuthRedirectHandler() {
  const searchParams = useSearchParams();

  useEffect(() => {
    const code = searchParams.get("code");
    if (code) {
      window.location.href = `/auth/callback?code=${encodeURIComponent(code)}`;
    }
  }, [searchParams]);

  return null;
}
