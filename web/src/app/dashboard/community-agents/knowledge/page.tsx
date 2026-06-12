"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Upload,
  Globe,
  Database,
  FileText,
  RefreshCcw,
  MoreHorizontal,
  Check,
  AlertTriangle,
  Clock,
  Plus,
  Trash2,
} from "lucide-react";
import { MOCK_KNOWLEDGE_SOURCES } from "@/lib/agent-mock-data";
import type { KnowledgeSource } from "@/lib/agent-types";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

const TYPE_ICONS: Record<KnowledgeSource["type"], typeof FileText> = {
  document: FileText,
  url: Globe,
  api: Upload,
  database: Database,
};

const STATUS_ICONS: Record<KnowledgeSource["status"], typeof Check> = {
  active: Check,
  processing: RefreshCcw,
  error: AlertTriangle,
};

function SourceRow({ source }: { source: KnowledgeSource }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const TypeIcon = TYPE_ICONS[source.type];
  const StatusIcon = STATUS_ICONS[source.status];

  return (
    <motion.div
      variants={itemVariants}
      className="group border border-white/10 bg-white/[0.02] hover:border-white/20 transition-all"
    >
      <div className="flex items-center gap-4 p-4 lg:p-5">
        <div className="w-10 h-10 bg-white/10 border border-white/10 flex items-center justify-center shrink-0">
          <TypeIcon className="w-4 h-4 text-white/60" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider truncate">
              {source.name}
            </h3>
            <span className={`text-[9px] uppercase tracking-widest px-2 py-0.5 font-bold ${
              source.status === "active"
                ? "bg-white text-black"
                : source.status === "processing"
                ? "bg-white/10 text-white/60"
                : "bg-red-500/10 text-red-400"
            }`}>
              <StatusIcon className={`w-2.5 h-2.5 inline mr-0.5 -mt-0.5 ${source.status === "processing" ? "animate-spin" : ""}`} />
              {source.status}
            </span>
          </div>
          <p className="text-xs text-white/40 mt-0.5">
            {source.type.toUpperCase()} &middot; {source.itemCount.toLocaleString()} items
          </p>
        </div>

        <div className="hidden md:flex items-center gap-4 shrink-0 text-[10px] text-white/40">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3 h-3" />
            <span className="font-mono">
              {new Date(source.lastSynced).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </span>
          </div>
        </div>

        <div className="relative shrink-0">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-2 text-white/30 hover:text-white hover:bg-white/5 transition-colors"
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1 w-40 bg-black border border-white/10 z-50 shadow-2xl">
                <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/5 transition-colors">
                  <RefreshCcw className="w-3.5 h-3.5" /> Sync Now
                </button>
                <div className="border-t border-white/5" />
                <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400/60 hover:text-red-400 hover:bg-white/5 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" /> Remove
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default function KnowledgePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">
            Knowledge Sources
          </h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">
            Manage data sources that power your agents.
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors">
          <Plus className="w-3.5 h-3.5" />
          Add Source
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Sources", value: MOCK_KNOWLEDGE_SOURCES.length },
          { label: "Active", value: MOCK_KNOWLEDGE_SOURCES.filter((s) => s.status === "active").length },
          { label: "Total Items", value: MOCK_KNOWLEDGE_SOURCES.reduce((a, s) => a + s.itemCount, 0).toLocaleString() },
          { label: "Processing", value: MOCK_KNOWLEDGE_SOURCES.filter((s) => s.status === "processing").length },
        ].map((stat) => (
          <div key={stat.label} className="p-4 border border-white/10 bg-white/[0.02]">
            <div className="text-2xl font-heading font-bold text-white">{stat.value}</div>
            <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Source list */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-3"
      >
        {MOCK_KNOWLEDGE_SOURCES.map((source) => (
          <SourceRow key={source.id} source={source} />
        ))}
      </motion.div>
    </div>
  );
}
