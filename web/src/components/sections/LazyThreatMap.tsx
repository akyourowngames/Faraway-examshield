"use client";

import dynamic from "next/dynamic";
import type { ThreatMapProps } from "@/components/sections/ThreatMap";

// Code-split the threat map (framer-motion + @svg-maps/india) out of the initial
// dashboard bundle. It is client-only and renders below-the-fold, so it is an
// ideal lazy-load target (audit §5/§7.3: frontend bundle).
const ThreatMap = dynamic(
  () => import("@/components/sections/ThreatMap").then((m) => m.ThreatMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center text-xs font-mono uppercase tracking-[0.2em] text-white/30">
        Loading threat map…
      </div>
    ),
  },
);

export function LazyThreatMap(props: ThreatMapProps) {
  return <ThreatMap {...props} />;
}
