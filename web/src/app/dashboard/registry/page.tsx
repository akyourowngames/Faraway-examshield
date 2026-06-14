"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  BookOpen,
  Plus,
  Shield,
  AlertTriangle,
  Search,
  Loader2,
  FileText,
  Eye,
} from "lucide-react";
import { listRegistryPapers, getRegistryStats, deleteRegistryPaper } from "@/lib/agent-api";
import type { RegistryPaper, RegistryStats } from "@/lib/agent-types";

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

const STATUS_COLORS: Record<string, string> = {
  registered: "bg-white text-black",
  received: "bg-white/10 text-white/60",
  in_transit: "bg-white/10 text-white/60",
  investigating: "bg-amber-500/10 text-amber-400",
  compromised: "bg-red-500/10 text-red-400",
};

const RISK_COLORS: Record<string, string> = {
  low: "text-white/40",
  medium: "text-amber-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

export default function RegistryDashboard() {
  const [papers, setPapers] = useState<RegistryPaper[]>([]);
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterExam, setFilterExam] = useState<string>("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    listRegistryPapers()
      .then((paperData) => {
        setPapers(paperData.papers || []);
        setFetchError(null);
      })
      .catch((err) => {
        console.error("Registry papers fetch failed:", err);
        setFetchError(err instanceof Error ? err.message : "Failed to load registry data.");
      })
      .finally(() => setLoading(false));

    getRegistryStats()
      .then((statsData) => setStats(statsData))
      .catch(() => {});
  }, []);

  const filtered = papers.filter((p) => {
    const q = search.toLowerCase();
    const matchSearch = !q || p.paperId.toLowerCase().includes(q) || p.exam.toLowerCase().includes(q) || p.centerName.toLowerCase().includes(q) || p.city.toLowerCase().includes(q);
    const matchExam = !filterExam || p.exam === filterExam;
    return matchSearch && matchExam;
  });

  const exams = [...new Set(papers.map((p) => p.exam))].sort();

  async function handleDelete(paperId: string) {
    if (!confirm(`Delete paper ${paperId}?`)) return;
    setDeleting(paperId);
    try {
      await deleteRegistryPaper(paperId);
      setPapers((prev) => prev.filter((p) => p.paperId !== paperId));
    } catch {
      // ignore
    } finally {
      setDeleting(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-white/30 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">
            Question Registry
          </h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">
            Protect and track official examination papers.
          </p>
        </div>
        <Link href="/dashboard/registry/upload"
          className="flex items-center gap-2 px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors">
          <Plus className="w-3.5 h-3.5" /> Upload Paper
        </Link>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Total Papers", value: stats.totalPapers, icon: FileText },
            { label: "Protected", value: stats.protectedPapers, icon: Shield },
            { label: "Compromised", value: stats.compromisedPapers, icon: AlertTriangle },
            { label: "Investigating", value: stats.investigatingPapers, icon: Eye },
          ].map((s) => (
            <div key={s.label} className="p-4 border border-white/10 bg-white/[0.02]">
              <div className="flex items-center gap-2 mb-2">
                <s.icon className="w-3.5 h-3.5 text-white/40" />
                <span className="text-[10px] uppercase tracking-widest text-white/40">{s.label}</span>
              </div>
              <div className="text-2xl font-heading font-bold text-white">{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Exam breakdown */}
      {stats && Object.keys(stats.byExam).length > 0 && (
        <div className="flex items-center gap-3 flex-wrap">
          <button onClick={() => setFilterExam("")}
            className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest border transition-colors ${!filterExam ? "border-white/30 bg-white/10 text-white" : "border-white/10 text-white/40 hover:border-white/20"}`}>
            All
          </button>
          {exams.map((exam) => (
            <button key={exam} onClick={() => setFilterExam(exam)}
              className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest border transition-colors ${filterExam === exam ? "border-white/30 bg-white/10 text-white" : "border-white/10 text-white/40 hover:border-white/20"}`}>
              {exam} <span className="text-white/25 ml-1">({stats.byExam[exam]})</span>
            </button>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
        <input type="text" placeholder="Search papers by ID, exam, center, city..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
      </div>

      {fetchError && (
        <div className="border border-red-500/20 bg-red-500/[0.05] p-4 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <div>
            <div className="text-xs font-bold text-red-400">Failed to load registry</div>
            <div className="text-[11px] text-red-400/60 mt-0.5">{fetchError}</div>
          </div>
        </div>
      )}

      {/* Papers table */}
      <div className="border border-white/10 bg-white/[0.02] overflow-hidden">
        <div className="grid grid-cols-7 gap-4 px-5 py-3 border-b border-white/10 text-[10px] uppercase tracking-widest text-white/30 font-bold">
          <div>Paper ID</div>
          <div>Exam</div>
          <div>Set</div>
          <div>Center</div>
          <div>City</div>
          <div>Status</div>
          <div>Risk</div>
        </div>
        <motion.div variants={{ show: { transition: { staggerChildren: 0.03 } } }} initial="hidden" animate="show">
          {filtered.length === 0 ? (
            <div className="px-5 py-12 text-center text-white/30 text-sm">No papers found.</div>
          ) : (
            filtered.map((paper) => (
              <motion.div key={paper.paperId} variants={itemVariants}
                className="grid grid-cols-7 gap-4 px-5 py-4 border-b border-white/5 hover:bg-white/[0.02] transition-colors items-center">
                <Link href={`/dashboard/registry/${paper.paperId}`} className="text-sm font-bold text-white hover:text-white/80 transition-colors font-mono">
                  {paper.paperId}
                </Link>
                <div className="text-xs text-white/60">{paper.exam} {paper.year}</div>
                <div className="text-xs text-white/60">{paper.paperSet}</div>
                <div className="text-xs text-white/40 truncate">{paper.centerCode}</div>
                <div className="text-xs text-white/40">{paper.city}</div>
                <span className={`text-[9px] uppercase tracking-widest px-2 py-0.5 font-bold w-fit ${STATUS_COLORS[paper.status] || "bg-white/10 text-white/60"}`}>
                  {paper.status}
                </span>
                <span className={`text-xs font-bold capitalize ${RISK_COLORS[paper.riskLevel] || "text-white/40"}`}>
                  {paper.riskLevel}
                </span>
              </motion.div>
            ))
          )}
        </motion.div>
      </div>
    </div>
  );
}
