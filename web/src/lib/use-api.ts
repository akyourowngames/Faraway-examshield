"use client";

import useSWR, { type KeyedMutator } from "swr";
import { apiFetch } from "@/lib/agent-api";

/**
 * Global query-cache hook (audit §7.2 — "No global state/query cache").
 *
 * Built on SWR: every request is keyed by its API path, so identical in-flight
 * or recently-resolved requests are deduplicated and shared across components
 * (no more duplicated `fetch` calls from `agent-api.ts`/`analysis-client.ts`).
 * SWR owns the cache, revalidation, and dedup; we only supply the fetcher.
 */

export interface ApiQueryState<T> {
  data: T | undefined;
  error: Error | undefined;
  isLoading: boolean;
  mutate: KeyedMutator<T>;
}

export interface ApiQueryOptions {
  /** When false, the request is not issued (e.g. awaiting a prerequisite). */
  enabled?: boolean;
  /** How long identical keys are deduplicated without a second fetch (ms). */
  dedupingIntervalMs?: number;
}

export function useApiQuery<T = unknown>(
  path: string,
  options?: ApiQueryOptions,
): ApiQueryState<T> {
  const enabled = options?.enabled ?? true;
  const dedupingIntervalMs = options?.dedupingIntervalMs ?? 30_000;

  const { data, error, isLoading, mutate } = useSWR<T, Error>(
    enabled ? path : null,
    () => apiFetch<T>(path),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: dedupingIntervalMs,
      keepPreviousData: true,
    },
  );

  return {
    data,
    error,
    isLoading: enabled && !data && !error ? Boolean(isLoading) : false,
    mutate,
  };
}
