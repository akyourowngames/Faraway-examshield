"use client";

import { forwardRef, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import IndiaMap from "@svg-maps/india";
import {
  X,
  AlertTriangle,
  ShieldCheck,
  Search,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  FileText,
} from "lucide-react";
import type { EvidenceListResponse } from "@/lib/evidence-types";
import { buildThreatMapCenters, type ThreatMapCenter } from "@/lib/map-centers";
import {
  formatEvidenceSource,
  formatEvidenceStatus,
  formatEvidenceTime,
} from "@/lib/evidence-format";

const MAP_W = 612;
const MAP_H = 696;
const MIN_ZOOM = 1;
const MAX_ZOOM = 8;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

// Convert lat/lng to SVG coordinates for the @svg-maps/india viewBox (0 0 612 696)
function latLngToSvg(lat: number, lng: number): { x: number; y: number } {
  const LAT_MIN = 7.5, LAT_MAX = 37.5;
  const LNG_MIN = 67.5, LNG_MAX = 97.5;
  const x = ((lng - LNG_MIN) / (LNG_MAX - LNG_MIN)) * MAP_W;
  const y = MAP_H - ((lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * MAP_H;
  return { x, y };
}

const STATUS_CONFIG = {
  compromised: {
    fill: "rgba(255,255,255,0.95)",
    ring: "rgba(255,255,255,0.4)",
    label: "COMPROMISED",
    dotSize: 6,
    rank: 2,
  },
  investigating: {
    fill: "rgba(255,255,255,0.65)",
    ring: "rgba(255,255,255,0.2)",
    label: "INVESTIGATING",
    dotSize: 4.5,
    rank: 1,
  },
  secure: {
    fill: "rgba(255,255,255,0.28)",
    ring: "rgba(255,255,255,0.12)",
    label: "SECURE",
    dotSize: 3,
    rank: 0,
  },
} as const;

type ViewState = { x: number; y: number; k: number };

type CenterIntel = {
  verdict: "leak-confirmed" | "under-investigation" | "no-leak";
  papers: { label: string; confidence: number | null }[];
  evidence: {
    id: string;
    filename: string;
    fileType: string;
    source: string;
    status: string;
    uploadedAt: string;
  }[];
  alertCount: number;
  lastActivityAt: string | null;
};

function deriveCenterIntel(
  centerCode: string,
  data: EvidenceListResponse,
): CenterIntel {
  const reports = data.forensicReports.filter((r) => r.centerCode === centerCode);
  const attributions = data.attributions.filter((a) => a.centerCode === centerCode);
  const alerts = data.alerts.filter((al) => al.centerCode === centerCode);

  const evidenceIds = new Set<string>([
    ...reports.map((r) => r.evidenceId),
    ...attributions.map((a) => a.evidenceId),
    ...alerts.map((al) => al.evidenceId),
  ]);

  const evidence = data.evidence
    .filter((item) => evidenceIds.has(item.evidenceId))
    .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt))
    .slice(0, 12)
    .map((item) => ({
      id: item.evidenceId,
      filename: item.filename,
      fileType: item.fileType,
      source: formatEvidenceSource(item.source),
      status: formatEvidenceStatus(item.status),
      uploadedAt: item.uploadedAt,
    }));

  const paperMap = new Map<string, number | null>();
  for (const report of reports) {
    if (!report.paperIdentified) continue;
    paperMap.set(report.paperIdentified, report.finalConfidence ?? null);
  }
  for (const attribution of attributions) {
    const key = attribution.matchedPaperId || attribution.matchedExam || "";
    if (!key || paperMap.has(key)) continue;
    paperMap.set(key, attribution.finalConfidence ?? null);
  }

  const hasConfirmed =
    reports.some((r) => r.status === "investigation-complete") ||
    attributions.some((a) => a.status === "compromised");
  const hasInvestigating =
    attributions.some((a) => a.status === "investigating") || reports.length > 0;

  const activityTimes = [
    ...reports.map((r) => r.timestamp),
    ...attributions.map((a) => a.createdAt),
    ...evidence.map((e) => e.uploadedAt),
  ].filter(Boolean).sort();

  return {
    verdict: hasConfirmed
      ? "leak-confirmed"
      : hasInvestigating
      ? "under-investigation"
      : "no-leak",
    papers: Array.from(paperMap.entries()).map(([label, confidence]) => ({
      label,
      confidence,
    })),
    evidence,
    alertCount: alerts.length,
    lastActivityAt: activityTimes.at(-1) ?? null,
  };
}

type ThreatMapProps = {
  evidenceData?: EvidenceListResponse;
};

export function ThreatMap({ evidenceData }: ThreatMapProps) {
  const [geoLookup, setGeoLookup] = useState<ThreatMapCenter[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [hoveredCenter, setHoveredCenter] = useState<ThreatMapCenter | null>(null);
  const [selectedCenter, setSelectedCenter] = useState<ThreatMapCenter | null>(null);
  const [filter, setFilter] = useState<"all" | "compromised" | "investigating" | "secure">("all");
  const [pulsingId, setPulsingId] = useState<string | null>(null);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [view, setView] = useState<ViewState>({ x: 0, y: 0, k: 1 });
  const [reloadKey, setReloadKey] = useState(0);

  const viewRef = useRef<ViewState>({ x: 0, y: 0, k: 1 });
  const animationFrameRef = useRef<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; viewX: number; viewY: number } | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/registry/centers.json")
      .then((r) => {
        if (!r.ok) throw new Error(`centers fetch failed: ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (!cancelled) {
          setGeoLookup((data.centers ?? []) as ThreatMapCenter[]);
          setLoadState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) setLoadState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const evidenceCenters = useMemo(() => {
    if (!evidenceData) return [];
    return buildThreatMapCenters(
      evidenceData,
      geoLookup.map((g) => ({
        centerCode: g.centerCode,
        name: g.name,
        city: g.city,
        state: g.state,
        lat: g.lat,
        lng: g.lng,
      })),
    );
  }, [evidenceData, geoLookup]);

  // Show the full configured grid, then enrich any center with live evidence.
  const markers = useMemo(() => {
    const byCode = new Map(evidenceCenters.map((c) => [c.centerCode, c]));
    const merged = geoLookup.map((g) => byCode.get(g.centerCode) ?? g);
    for (const center of evidenceCenters) {
      if (!geoLookup.some((g) => g.centerCode === center.centerCode)) {
        merged.push(center);
      }
    }
    return merged.sort(
      (a, b) =>
        STATUS_CONFIG[a.status].rank - STATUS_CONFIG[b.status].rank ||
        b.risk - a.risk,
    );
  }, [geoLookup, evidenceCenters]);

  useEffect(() => {
    if (markers.length === 0) return;
    const compromised = markers.filter((c) => c.status === "compromised");
    if (compromised.length === 0) return;
    const interval = setInterval(() => {
      const random = compromised[Math.floor(Math.random() * compromised.length)];
      setPulsingId(random.id);
      const timeout = setTimeout(() => setPulsingId(null), 3000);
      return () => clearTimeout(timeout);
    }, 6000);
    return () => clearInterval(interval);
  }, [markers]);

  const filtered = filter === "all" ? markers : markers.filter((c) => c.status === filter);

  const stats = {
    compromised: markers.filter((c) => c.status === "compromised").length,
    investigating: markers.filter((c) => c.status === "investigating").length,
    secure: markers.filter((c) => c.status === "secure").length,
  };

  const nationalRisk = markers.length
    ? Math.round(markers.reduce((a, c) => a + c.risk, 0) / markers.length)
    : 0;
  const riskLabel = nationalRisk >= 70 ? "CRITICAL" : nationalRisk >= 40 ? "ELEVATED" : "LOW";

  const commitView = useCallback((next: ViewState) => {
    const k = clamp(Number.isFinite(next.k) ? next.k : MIN_ZOOM, MIN_ZOOM, MAX_ZOOM);
    const width = MAP_W / k;
    const height = MAP_H / k;
    const safe = {
      x: clamp(Number.isFinite(next.x) ? next.x : 0, 0, MAP_W - width),
      y: clamp(Number.isFinite(next.y) ? next.y : 0, 0, MAP_H - height),
      k,
    };
    viewRef.current = safe;
    setView(safe);
  }, []);

  const animateView = useCallback((target: ViewState) => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    const start = { ...viewRef.current };
    const duration = 280;
    const startedAt = performance.now();
    const easeOutQuint = (progress: number) => 1 - Math.pow(1 - progress, 5);

    const frame = (time: number) => {
      const progress = clamp((time - startedAt) / duration, 0, 1);
      const eased = easeOutQuint(progress);
      commitView({
        x: start.x + (target.x - start.x) * eased,
        y: start.y + (target.y - start.y) * eased,
        k: start.k + (target.k - start.k) * eased,
      });
      if (progress < 1) {
        animationFrameRef.current = requestAnimationFrame(frame);
      } else {
        animationFrameRef.current = null;
      }
    };

    animationFrameRef.current = requestAnimationFrame(frame);
  }, [commitView]);

  useEffect(() => {
    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  const zoomAt = useCallback(
    (factor: number, focalX: number, focalY: number) => {
      const el = svgRef.current;
      if (!el) return;

      const current = viewRef.current;
      const currentW = MAP_W / current.k;
      const currentH = MAP_H / current.k;
      const scale = Math.min(el.clientWidth / currentW, el.clientHeight / currentH);
      const offsetX = (el.clientWidth - currentW * scale) / 2;
      const offsetY = (el.clientHeight - currentH * scale) / 2;
      const localX = clamp((focalX - offsetX) / scale, 0, currentW);
      const localY = clamp((focalY - offsetY) / scale, 0, currentH);
      const pointX = current.x + localX;
      const pointY = current.y + localY;

      const nextK = clamp(current.k * factor, MIN_ZOOM, MAX_ZOOM);
      if (nextK === current.k) return;

      const ratio = current.k / nextK;
      animateView({
        x: pointX - localX * ratio,
        y: pointY - localY * ratio,
        k: nextK,
      });
    },
    [animateView],
  );

  const zoomCenter = useCallback(
    (factor: number) => {
      const el = svgRef.current;
      if (!el) return;
      zoomAt(factor, el.clientWidth / 2, el.clientHeight / 2);
    },
    [zoomAt],
  );

  const resetView = useCallback(() => {
    animateView({ x: 0, y: 0, k: 1 });
  }, [animateView]);

  const panBy = useCallback(
    (dx: number, dy: number) => {
      const current = viewRef.current;
      const currentW = MAP_W / current.k;
      const currentH = MAP_H / current.k;
      animateView({
        x: current.x + dx * currentW,
        y: current.y + dy * currentH,
        k: current.k,
      });
    },
    [animateView],
  );

  const handleMapKeyDown = (event: React.KeyboardEvent<SVGSVGElement>) => {
    if ((event.target as Element).closest?.("[data-marker]")) return;
    const step = 0.18;
    switch (event.key) {
      case "ArrowLeft":
        event.preventDefault();
        panBy(-step, 0);
        break;
      case "ArrowRight":
        event.preventDefault();
        panBy(step, 0);
        break;
      case "ArrowUp":
        event.preventDefault();
        panBy(0, -step);
        break;
      case "ArrowDown":
        event.preventDefault();
        panBy(0, step);
        break;
      case "+":
      case "=":
        event.preventDefault();
        zoomCenter(1.4);
        break;
      case "-":
      case "_":
        event.preventDefault();
        zoomCenter(1 / 1.4);
        break;
      case "0":
        event.preventDefault();
        resetView();
        break;
      default:
        break;
    }
  };

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      const factor = event.deltaY < 0 ? 1.4 : 1 / 1.4;
      zoomAt(factor, event.clientX - rect.left, event.clientY - rect.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const vw = MAP_W / view.k;
  const vh = MAP_H / view.k;
  const vx = clamp(view.x, 0, MAP_W - vw);
  const vy = clamp(view.y, 0, MAP_H - vh);
  const viewBox = `${vx} ${vy} ${vw} ${vh}`;

  const openCenter = useCallback((center: ThreatMapCenter) => {
    triggerRef.current = document.activeElement as HTMLElement | null;
    setSelectedCenter(center);
  }, []);

  const closeCenter = useCallback(() => {
    setSelectedCenter(null);
    requestAnimationFrame(() => triggerRef.current?.focus?.());
  }, []);

  useEffect(() => {
    if (!selectedCenter) return;
    const dialog = dialogRef.current;
    if (!dialog) return;

    closeButtonRef.current?.focus();

    const focusables = () =>
      Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (event.shiftKey) {
        if (active === first || !dialog.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !dialog.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    };

    dialog.addEventListener("keydown", onKeyDown);
    return () => dialog.removeEventListener("keydown", onKeyDown);
  }, [selectedCenter]);

  const onPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return;
    if ((event.target as Element).closest?.("[data-marker]")) return;
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      viewX: viewRef.current.x,
      viewY: viewRef.current.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    const el = svgRef.current;
    if (!drag || !el) return;

    const currentW = MAP_W / viewRef.current.k;
    const currentH = MAP_H / viewRef.current.k;
    const scale = Math.min(el.clientWidth / currentW, el.clientHeight / currentH);
    const dx = (event.clientX - drag.startX) / scale;
    const dy = (event.clientY - drag.startY) / scale;

    commitView({
      x: drag.viewX - dx,
      y: drag.viewY - dy,
      k: viewRef.current.k,
    });
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  return (
    <div className="relative w-full h-full flex flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-white/10 shrink-0">
        <div className="flex items-center gap-3">
          <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">
            National Examination Security Map
          </h3>
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-40" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-white" />
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] uppercase tracking-widest text-white/30 font-mono">
            {markers.length} centers tracked
          </span>
          <span className="text-[10px] uppercase tracking-widest text-white/30 font-mono">National Threat Index</span>
          <span className="text-base font-bold font-heading text-white">{nationalRisk}</span>
          <span className="text-white/20 text-xs font-mono">/ 100</span>
          <span className={`text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 border ${
            nationalRisk >= 70
              ? "border-white/40 text-white bg-white/10"
              : nationalRisk >= 40
              ? "border-white/20 text-white/70 bg-white/5"
              : "border-white/10 text-white/40"
          }`}>
            {riskLabel}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1 px-5 py-2 border-b border-white/5 shrink-0">
        {(["all", "compromised", "investigating", "secure"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            aria-pressed={filter === f}
            className={`px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2 ${
              filter === f
                ? "border-white/30 bg-white/10 text-white"
                : "border-transparent text-white/30 hover:bg-white/5 hover:text-white/60"
            }`}
          >
            {f === "all"
              ? `Evidence (${markers.length})`
              : f === "compromised"
              ? `● ${stats.compromised} Compromised`
              : f === "investigating"
              ? `◐ ${stats.investigating} Investigating`
              : `○ ${stats.secure} Secure`}
          </button>
        ))}
      </div>

      <div className="flex-1 relative overflow-hidden bg-[#040406]">
        <div className="absolute inset-0 pointer-events-none z-10 bg-[radial-gradient(ellipse_at_center,transparent_40%,#040406_95%)]" />
        <div className="absolute inset-0 opacity-[0.07] bg-[linear-gradient(to_right,#ffffff_1px,transparent_1px),linear-gradient(to_bottom,#ffffff_1px,transparent_1px)] bg-[size:32px_32px]" />

        <svg
          ref={svgRef}
          viewBox={viewBox}
          tabIndex={0}
          className="w-full h-full select-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/50 focus-visible:outline-offset-2"
          style={{ display: "block", touchAction: "none" }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onKeyDown={handleMapKeyDown}
          aria-label="Examination security map. Arrow keys pan, plus and minus zoom, zero resets."
        >
          {IndiaMap.locations.map((loc: { id: string; path: string }) => (
            <path
              key={loc.id}
              d={loc.path}
              fill="#0c0e14"
              stroke="#ffffff18"
              strokeWidth={0.8 / view.k}
              strokeLinejoin="round"
            />
          ))}

          {filtered.map((center) => {
            const cfg = STATUS_CONFIG[center.status];
            const { x, y } = latLngToSvg(center.lat, center.lng);
            const isPulsing = pulsingId === center.id;
            const isFocused = focusedId === center.id;
            const baseR = cfg.dotSize;
            const r = (isPulsing ? baseR + 1.5 : baseR) / view.k;
            const pulseDelay = (center.id.charCodeAt(center.id.length - 1) % 6) * 0.35;

            return (
              <g
                key={center.id}
                transform={`translate(${x}, ${y})`}
                className="cursor-pointer focus:outline-none"
                role="button"
                tabIndex={0}
                data-marker
                aria-label={`${center.centerCode} ${center.name}, ${cfg.label}`}
                onMouseEnter={() => setHoveredCenter(center)}
                onMouseLeave={() => setHoveredCenter(null)}
                onFocus={() => {
                  setFocusedId(center.id);
                  setHoveredCenter(center);
                }}
                onBlur={() => {
                  setFocusedId(null);
                  setHoveredCenter(null);
                }}
                onPointerDown={(event) => event.stopPropagation()}
                onClick={() => openCenter(center)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openCenter(center);
                  }
                }}
              >
                <circle
                  r={(baseR + 9) / view.k}
                  fill="transparent"
                  style={{ pointerEvents: "all" }}
                />
                {center.status === "compromised" && (
                  <circle
                    className="map-pulse"
                    r={(baseR + 5) / view.k}
                    fill="none"
                    stroke="rgba(255,255,255,0.35)"
                    strokeWidth={1 / view.k}
                    style={{ animationDelay: `${pulseDelay}s` }}
                  />
                )}
                {center.status === "investigating" && (
                  <circle
                    r={(baseR + 2.5) / view.k}
                    fill="none"
                    stroke="rgba(255,255,255,0.16)"
                    strokeWidth={0.8 / view.k}
                  />
                )}
                {isFocused && (
                  <circle
                    r={(baseR + 7) / view.k}
                    fill="none"
                    stroke="rgba(255,255,255,0.9)"
                    strokeWidth={1.2 / view.k}
                  />
                )}
                <circle
                  r={r}
                  fill={cfg.fill}
                  stroke={cfg.ring}
                  strokeWidth={1 / view.k}
                  style={{
                    filter:
                      center.status === "compromised"
                        ? "drop-shadow(0 0 3px rgba(255,255,255,0.6))"
                        : "none",
                  }}
                />
                {(isFocused || isPulsing || view.k >= 1.35) && center.status !== "secure" && (
                  <text
                    x={0}
                    y={-(baseR + 8) / view.k}
                    textAnchor="middle"
                    fill="rgba(255,255,255,0.92)"
                    stroke="#040406"
                    strokeWidth={2.6 / view.k}
                    paintOrder="stroke"
                    fontSize={8 / view.k}
                    fontWeight={600}
                    fontFamily="var(--font-heading)"
                    style={{ pointerEvents: "none", letterSpacing: "0.06em" }}
                  >
                    {center.city.toUpperCase()}
                  </text>
                )}
                {view.k >= 2.4 && (
                  <text
                    x={0}
                    y={(baseR + 11) / view.k}
                    textAnchor="middle"
                    fill="rgba(255,255,255,0.55)"
                    stroke="#040406"
                    strokeWidth={2.2 / view.k}
                    paintOrder="stroke"
                    fontSize={6 / view.k}
                    fontFamily="var(--font-heading)"
                    style={{ pointerEvents: "none", letterSpacing: "0.08em" }}
                  >
                    {center.centerCode} · {center.name}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {loadState === "loading" && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#040406]/60 backdrop-blur-[2px]">
            <div className="text-center">
              <div className="mx-auto mb-3 h-5 w-5 animate-spin rounded-full border border-white/20 border-t-white" />
              <div className="text-xs uppercase tracking-[0.2em] text-white/50">Locating centers…</div>
            </div>
          </div>
        )}

        {loadState === "error" && (
          <div className="absolute inset-0 z-20 flex items-center justify-center px-6">
            <div className="border border-white/10 bg-black/80 px-6 py-4 text-center backdrop-blur-md max-w-xs">
              <div className="text-xs uppercase tracking-[0.2em] text-white/60">Map unavailable</div>
              <p className="text-[11px] text-white/35 mt-2">Center coordinates could not be loaded.</p>
              <button
                onClick={() => {
                  setLoadState("loading");
                  setReloadKey((key) => key + 1);
                }}
                className="mt-3 border border-white/20 bg-white/5 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-white hover:bg-white/10"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {loadState === "ready" && markers.length === 0 && (
          <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
            <div className="border border-white/10 bg-black/80 px-6 py-4 text-center backdrop-blur-md">
              <div className="text-xs uppercase tracking-[0.2em] text-white/50">No Evidence Markers</div>
              <p className="text-[11px] text-white/35 mt-2 max-w-xs">
                Map markers appear only when forensic evidence identifies an examination center.
              </p>
            </div>
          </div>
        )}

        <div className="absolute bottom-4 right-4 z-20 flex flex-col items-center gap-1.5">
          <button
            onClick={() => zoomCenter(1.4)}
            aria-label="Zoom in"
            disabled={view.k >= MAX_ZOOM}
            className="flex h-11 w-11 items-center justify-center border border-white/15 bg-black/70 text-white/70 backdrop-blur-md transition-colors hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:border-white/5 disabled:text-white/20 disabled:hover:bg-black/70 disabled:hover:text-white/20"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            onClick={() => zoomCenter(1 / 1.4)}
            aria-label="Zoom out"
            disabled={view.k <= MIN_ZOOM}
            className="flex h-11 w-11 items-center justify-center border border-white/15 bg-black/70 text-white/70 backdrop-blur-md transition-colors hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:border-white/5 disabled:text-white/20 disabled:hover:bg-black/70 disabled:hover:text-white/20"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            onClick={resetView}
            aria-label="Reset map view"
            className="flex h-11 w-11 items-center justify-center border border-white/15 bg-black/70 text-white/70 backdrop-blur-md transition-colors hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/60 focus-visible:outline-offset-2"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <span className="mt-1 text-[9px] font-mono uppercase tracking-widest text-white/30">
            {Math.round(view.k * 100)}%
          </span>
        </div>

        <AnimatePresence>
          {hoveredCenter && (
            <motion.div
              key={hoveredCenter.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.15 }}
              className="absolute bottom-4 left-1/2 -translate-x-1/2 z-30 pointer-events-none"
            >
              <div className="bg-black/95 border border-white/10 px-4 py-3 min-w-[220px] backdrop-blur-md shadow-2xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-heading font-bold text-white text-sm tracking-wider">
                    {hoveredCenter.centerCode}
                  </span>
                  <span className={`text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 border ${
                    hoveredCenter.status === "compromised"
                      ? "border-white/30 text-white bg-white/10"
                      : hoveredCenter.status === "investigating"
                      ? "border-white/15 text-white/60"
                      : "border-white/10 text-white/30"
                  }`}>
                    {STATUS_CONFIG[hoveredCenter.status].label}
                  </span>
                </div>
                <p className="text-xs text-white/40 mb-2 truncate">{hoveredCenter.name}</p>
                <div className="grid grid-cols-2 gap-x-6 gap-y-0.5">
                  {[
                    ["Risk", `${hoveredCenter.risk} / 100`],
                    ["Cases", String(hoveredCenter.activeCases)],
                    ["Evidence", String(hoveredCenter.evidenceCount)],
                    ["State", hoveredCenter.state],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between text-[10px] font-mono">
                      <span className="text-white/30 uppercase">{k}</span>
                      <span className="text-white/70 font-bold">{v}</span>
                    </div>
                  ))}
                </div>
                <p className="text-[9px] text-white/20 mt-2 font-mono">Enter for full intelligence</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex items-center justify-between gap-8 px-5 py-2.5 border-t border-white/5 bg-black/50 shrink-0">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-white/90 shadow-[0_0_6px_rgba(255,255,255,0.7)]" />
            <span className="text-[10px] uppercase tracking-widest text-white/40 font-mono">Compromised</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-white/55 ring-1 ring-white/20" />
            <span className="text-[10px] uppercase tracking-widest text-white/40 font-mono">Investigating</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
            <span className="text-[10px] uppercase tracking-widest text-white/40 font-mono">Secure</span>
          </div>
        </div>
        <span className="hidden xl:inline text-[10px] uppercase tracking-widest text-white/25 font-mono">
          Scroll to zoom · drag to pan
        </span>
      </div>

      <AnimatePresence>
        {selectedCenter && (
          <CenterIntelPanel
            ref={dialogRef}
            center={selectedCenter}
            intel={
              evidenceData
                ? deriveCenterIntel(selectedCenter.centerCode, evidenceData)
                : null
            }
            onClose={closeCenter}
            closeButtonRef={closeButtonRef}
          />
        )}
      </AnimatePresence>

      <style>{`
        .map-pulse {
          transform-box: fill-box;
          transform-origin: center;
          animation: map-pulse 2.4s ease-out infinite;
        }
        @keyframes map-pulse {
          0%   { transform: scale(0.7); opacity: 0.7; }
          60%  { transform: scale(1.8); opacity: 0.15; }
          100% { transform: scale(2.4); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

type CenterIntelPanelProps = {
  center: ThreatMapCenter;
  intel: CenterIntel | null;
  onClose: () => void;
  closeButtonRef: React.RefObject<HTMLButtonElement | null>;
};

const VERDICT_CONFIG = {
  "leak-confirmed": {
    label: "Paper Leak Confirmed",
    icon: AlertTriangle,
    border: "border-white/30",
    bg: "bg-white/10",
    text: "text-white",
  },
  "under-investigation": {
    label: "Under Investigation",
    icon: Search,
    border: "border-white/20",
    bg: "bg-white/[0.04]",
    text: "text-white/80",
  },
  "no-leak": {
    label: "No Leak Detected",
    icon: ShieldCheck,
    border: "border-white/10",
    bg: "bg-transparent",
    text: "text-white/50",
  },
} as const;

const CenterIntelPanel = forwardRef<HTMLDivElement, CenterIntelPanelProps>(
  function CenterIntelPanel(
    { center, intel, onClose, closeButtonRef },
    ref,
  ) {
    return (
      <motion.div
        ref={ref}
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 30, stiffness: 280 }}
        role="dialog"
        aria-modal="true"
        aria-label={`${center.centerCode} center intelligence`}
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }}
        className="absolute right-0 top-0 bottom-0 w-80 bg-black/96 border-l border-white/10 flex flex-col z-40 backdrop-blur-xl"
      >
        <div className="p-4 border-b border-white/10 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-widest text-white/30 font-mono mb-0.5">
              Center Intelligence
            </div>
            <h4 className="font-heading font-bold text-white text-lg tracking-wider truncate">
              {center.centerCode}
            </h4>
            <p className="text-[11px] text-white/40 truncate">
              {center.name} · {center.city}, {center.state}
            </p>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            aria-label="Close center intelligence"
            className="p-1.5 shrink-0 hover:bg-white/10 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-white/60"
          >
            <X className="w-4 h-4 text-white/50" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {intel === null ? (
            <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
              <div className="h-5 w-5 animate-spin rounded-full border border-white/20 border-t-white" />
              <div className="text-[10px] uppercase tracking-widest text-white/30 font-mono">
                Loading intel…
              </div>
            </div>
          ) : (
            <>
              <motion.div
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: 0.05 }}
                className={`flex items-center gap-3 p-3 border ${VERDICT_CONFIG[intel.verdict].border} ${VERDICT_CONFIG[intel.verdict].bg}`}
              >
                {(() => {
                  const VerdictIcon = VERDICT_CONFIG[intel.verdict].icon;
                  return (
                    <VerdictIcon
                      className={`w-5 h-5 shrink-0 ${VERDICT_CONFIG[intel.verdict].text}`}
                    />
                  );
                })()}
                <div className="min-w-0">
                  <div className={`text-xs font-bold uppercase tracking-widest ${VERDICT_CONFIG[intel.verdict].text}`}>
                    {VERDICT_CONFIG[intel.verdict].label}
                  </div>
                  {intel.lastActivityAt && (
                    <div className="text-[10px] text-white/30 font-mono mt-0.5">
                      Last activity {formatEvidenceTime(intel.lastActivityAt)}
                    </div>
                  )}
                </div>
                {intel.alertCount > 0 && (
                  <span className="ml-auto shrink-0 text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 bg-white/15 text-white">
                    {intel.alertCount} {intel.alertCount === 1 ? "alert" : "alerts"}
                  </span>
                )}
              </motion.div>

              <motion.div
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: 0.12 }}
              >
                <div className="text-[10px] uppercase tracking-widest text-white/20 font-mono mb-2">
                  Affected Papers
                </div>
                {intel.papers.length === 0 ? (
                  <p className="text-[11px] text-white/30 font-mono">
                    No papers attributed to this center yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {intel.papers.map((paper, index) => (
                      <motion.div
                        key={paper.label}
                        initial={{ opacity: 0, x: 16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.22, delay: 0.15 + index * 0.05 }}
                        className="flex items-center gap-3 p-2.5 bg-white/[0.03] border border-white/5"
                      >
                        <FileText className="w-4 h-4 text-white/50 shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="text-xs text-white/80 truncate">{paper.label}</div>
                          {paper.confidence !== null && (
                            <div className="text-[9px] font-mono text-white/30 mt-0.5">
                              Match confidence {Math.round(paper.confidence * 100)}%
                            </div>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>

              <motion.div
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: 0.18 }}
              >
                <div className="text-[10px] uppercase tracking-widest text-white/20 font-mono mb-2">
                  Evidence Stream ({intel.evidence.length})
                </div>
                {intel.evidence.length === 0 ? (
                  <p className="text-[11px] text-white/30 font-mono">
                    No evidence linked to this center yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {intel.evidence.map((item, index) => (
                      <motion.div
                        key={item.id}
                        initial={{ opacity: 0, x: 16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.22, delay: 0.2 + index * 0.04 }}
                        className="p-2.5 bg-white/[0.03] border border-white/5"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs text-white/80 truncate">{item.filename}</span>
                          <span className="shrink-0 text-[9px] font-mono text-white/30">
                            {formatEvidenceTime(item.uploadedAt)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-1.5 text-[9px] uppercase tracking-widest font-mono">
                          <span className="text-white/40">{item.source}</span>
                          <span className="text-white/20">·</span>
                          <span className="text-white/40">{item.status}</span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>
            </>
          )}
        </div>
      </motion.div>
    );
  },
);
