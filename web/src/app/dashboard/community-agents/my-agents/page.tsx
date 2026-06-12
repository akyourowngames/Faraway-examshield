"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Plus,
  MoreHorizontal,
  BookOpen,
  MessageSquare,
  Clock,
  Pause,
  Play,
  Trash2,
  ExternalLink,
} from "lucide-react";
import { MOCK_AGENTS } from "@/lib/agent-mock-data";
import type { Agent, AgentStatus } from "@/lib/agent-types";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

const STATUS_CONFIG: Record<AgentStatus, { label: string; classes: string; dotClass: string }> = {
  active: { label: "Active", classes: "bg-white text-black", dotClass: "bg-black" },
  draft: { label: "Draft", classes: "bg-white/10 text-white/60", dotClass: "bg-white/60" },
  paused: { label: "Paused", classes: "bg-white/10 text-white/60", dotClass: "bg-white/40" },
  archived: { label: "Archived", classes: "bg-white/5 text-white/30", dotClass: "bg-white/30" },
};

function AgentRow({ agent }: { agent: Agent }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const status = STATUS_CONFIG[agent.status];

  return (
    <motion.div
      variants={itemVariants}
      className="group border border-white/10 bg-white/[0.02] hover:border-white/20 transition-all relative"
    >
      <div className="flex items-center gap-4 p-4 lg:p-5">
        {/* Avatar */}
        <div className="w-10 h-10 bg-white/10 border border-white/10 flex items-center justify-center shrink-0">
          <span className="text-xs font-bold font-heading text-white">{agent.avatar}</span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider truncate">
              {agent.name}
            </h3>
            <span className={`text-[9px] uppercase tracking-widest px-2 py-0.5 font-bold ${status.classes}`}>
              <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${status.dotClass}`} />
              {status.label}
            </span>
          </div>
          <p className="text-xs text-white/40 mt-0.5 truncate">{agent.description}</p>
        </div>

        {/* Metrics (desktop) */}
        <div className="hidden md:flex items-center gap-6 shrink-0">
          <div className="text-center">
            <div className="text-lg font-heading font-bold text-white">{agent.knowledgeCount}</div>
            <div className="text-[9px] uppercase tracking-widest text-white/30">Knowledge</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-heading font-bold text-white">{agent.conversationCount}</div>
            <div className="text-[9px] uppercase tracking-widest text-white/30">Conversations</div>
          </div>
          <div className="text-center w-24">
            <div className="flex items-center gap-1 justify-center text-white/40">
              <Clock className="w-3 h-3" />
              <span className="text-[10px] font-mono">
                {new Date(agent.lastActivity).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
              </span>
            </div>
            <div className="text-[9px] uppercase tracking-widest text-white/30">Last Active</div>
          </div>
        </div>

        {/* Actions */}
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
              <div className="absolute right-0 top-full mt-1 w-44 bg-black border border-white/10 z-50 shadow-2xl">
                <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/5 transition-colors">
                  <ExternalLink className="w-3.5 h-3.5" /> Open
                </button>
                <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/5 transition-colors">
                  <BookOpen className="w-3.5 h-3.5" /> Knowledge
                </button>
                {agent.status === "active" ? (
                  <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/5 transition-colors">
                    <Pause className="w-3.5 h-3.5" /> Pause
                  </button>
                ) : (
                  <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/5 transition-colors">
                    <Play className="w-3.5 h-3.5" /> Activate
                  </button>
                )}
                <div className="border-t border-white/5" />
                <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400/60 hover:text-red-400 hover:bg-white/5 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Mobile metrics */}
      <div className="md:hidden flex items-center gap-4 px-4 pb-4 text-[10px] text-white/40">
        <span className="flex items-center gap-1"><BookOpen className="w-3 h-3" /> {agent.knowledgeCount} sources</span>
        <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" /> {agent.conversationCount} chats</span>
        <span className="flex items-center gap-1 ml-auto"><Clock className="w-3 h-3" /> {new Date(agent.lastActivity).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
      </div>
    </motion.div>
  );
}

export default function MyAgentsPage() {
  const [statusFilter, setStatusFilter] = useState<AgentStatus | "all">("all");

  const agents = useMemo(() => {
    let list = [...MOCK_AGENTS];
    if (statusFilter !== "all") {
      list = list.filter((a) => a.status === statusFilter);
    }
    return list;
  }, [statusFilter]);

  const counts = useMemo(() => ({
    all: MOCK_AGENTS.length,
    active: MOCK_AGENTS.filter((a) => a.status === "active").length,
    draft: MOCK_AGENTS.filter((a) => a.status === "draft").length,
    paused: MOCK_AGENTS.filter((a) => a.status === "paused").length,
  }), []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">
            My Agents
          </h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">
            Manage your deployed AI agents.
          </p>
        </div>
        <Link href="/dashboard/community-agents/create">
          <div className="flex items-center gap-2 px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors cursor-pointer">
            <Plus className="w-3.5 h-3.5" />
            New Agent
          </div>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {(["all", "active", "draft", "paused"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`p-4 border text-left transition-colors ${
              statusFilter === s
                ? "border-white/25 bg-white/[0.04]"
                : "border-white/10 bg-white/[0.02] hover:border-white/15"
            }`}
          >
            <div className="text-2xl font-heading font-bold text-white">{counts[s]}</div>
            <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">
              {s === "all" ? "Total" : s}
            </div>
          </button>
        ))}
      </div>

      {/* Agent list */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-3"
      >
        {agents.map((agent) => (
          <AgentRow key={agent.id} agent={agent} />
        ))}
      </motion.div>

      {agents.length === 0 && (
        <div className="border border-dashed border-white/10 bg-white/[0.02] flex flex-col items-center justify-center text-center py-20">
          <Plus className="w-8 h-8 text-white/25 mb-4" />
          <div className="text-xl font-heading uppercase tracking-widest text-white">No Agents</div>
          <p className="text-sm text-white/45 mt-3 max-w-sm">
            Create your first agent to get started.
          </p>
          <Link href="/dashboard/community-agents/create" className="mt-6">
            <div className="px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors cursor-pointer">
              Create Agent
            </div>
          </Link>
        </div>
      )}
    </div>
  );
}
