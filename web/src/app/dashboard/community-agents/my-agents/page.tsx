"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Plus, MoreHorizontal, BookOpen, MessageSquare, Clock, Pause, Play, Trash2, ExternalLink, Loader2 } from "lucide-react";
import { listAgents, deleteAgent, updateAgent } from "@/lib/agent-api";
import type { Agent, AgentStatus } from "@/lib/agent-types";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

const STATUS_CONFIG: Record<string, { label: string; classes: string; dotClass: string }> = {
  active: { label: "Active", classes: "bg-white text-black", dotClass: "bg-black" },
  draft: { label: "Draft", classes: "bg-white/10 text-white/60", dotClass: "bg-white/60" },
  paused: { label: "Paused", classes: "bg-white/10 text-white/60", dotClass: "bg-white/40" },
  processing: { label: "Processing", classes: "bg-white/10 text-white/60", dotClass: "bg-white/40 animate-pulse" },
  deploying: { label: "Deploying", classes: "bg-white/10 text-white/60", dotClass: "bg-white/40 animate-pulse" },
  failed: { label: "Failed", classes: "bg-red-500/10 text-red-400/60", dotClass: "bg-red-400/60" },
};

function AgentRow({ agent, onRefresh }: { agent: Agent; onRefresh: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [toggling, setToggling] = useState(false);
  const status = STATUS_CONFIG[agent.status] || STATUS_CONFIG.draft;

  async function handleToggleStatus() {
    setToggling(true);
    try {
      const newStatus: AgentStatus = agent.status === "active" ? "paused" : "active";
      await updateAgent(agent.id, { status: newStatus });
      onRefresh();
    } catch {
      // ignore
    } finally {
      setToggling(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this agent?")) return;
    try {
      await deleteAgent(agent.id);
      onRefresh();
    } catch {
      // ignore
    }
  }

  return (
    <motion.div variants={itemVariants} className="group border border-white/10 bg-white/[0.02] hover:border-white/20 transition-all relative">
      <div className="flex items-center gap-4 p-4 lg:p-5">
        <div className="w-10 h-10 bg-white/10 border border-white/10 flex items-center justify-center shrink-0">
          <span className="text-xs font-bold font-heading text-white">{agent.avatar || agent.name.slice(0, 2).toUpperCase()}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Link href={`/dashboard/community-agents/agent/${agent.id}`}>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider truncate hover:text-white/80 transition-colors cursor-pointer">{agent.name}</h3>
            </Link>
            <span className={`text-[9px] uppercase tracking-widest px-2 py-0.5 font-bold ${status.classes}`}>
              <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${status.dotClass}`} />
              {status.label}
            </span>
          </div>
          <p className="text-xs text-white/40 mt-0.5 truncate">{agent.description}</p>
        </div>
        <div className="hidden md:flex items-center gap-6 shrink-0">
          <div className="text-center">
            <div className="text-lg font-heading font-bold text-white">{agent.knowledgeCount}</div>
            <div className="text-[9px] uppercase tracking-widest text-white/30">Knowledge</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-heading font-bold text-white">{agent.conversationCount}</div>
            <div className="text-[9px] uppercase tracking-widest text-white/30">Chats</div>
          </div>
          <div className="text-center w-24">
            <div className="flex items-center gap-1 justify-center text-white/40">
              <Clock className="w-3 h-3" />
              <span className="text-[10px] font-mono">{new Date(agent.updatedAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
            </div>
            <div className="text-[9px] uppercase tracking-widest text-white/30">Updated</div>
          </div>
        </div>
        <div className="relative shrink-0">
          <button onClick={() => setMenuOpen(!menuOpen)} className="p-2 text-white/30 hover:text-white hover:bg-white/5 transition-colors">
            <MoreHorizontal className="w-4 h-4" />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1 w-44 bg-black border border-white/10 z-50 shadow-2xl">
                <Link href={`/dashboard/community-agents/agent/${agent.id}`}>
                  <button className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/5 transition-colors">
                    <ExternalLink className="w-3.5 h-3.5" /> Open
                  </button>
                </Link>
                <button onClick={handleToggleStatus} disabled={toggling}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/5 transition-colors disabled:opacity-50">
                  {toggling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : agent.status === "active" ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                  {agent.status === "active" ? "Pause" : "Activate"}
                </button>
                <div className="border-t border-white/5" />
                <button onClick={handleDelete} className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400/60 hover:text-red-400 hover:bg-white/5 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default function MyAgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const fetchAgents = useCallback(async () => {
    try {
      const data = await listAgents(statusFilter === "all" ? undefined : statusFilter);
      setAgents(data.agents);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  const counts = {
    all: agents.length,
    active: agents.filter((a) => a.status === "active").length,
    draft: agents.filter((a) => a.status === "draft").length,
    paused: agents.filter((a) => a.status === "paused").length,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">My Agents</h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">Manage your deployed AI agents.</p>
        </div>
        <Link href="/dashboard/community-agents/create">
          <div className="flex items-center gap-2 px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors cursor-pointer">
            <Plus className="w-3.5 h-3.5" /> New Agent
          </div>
        </Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {(["all", "active", "draft", "paused"] as const).map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`p-4 border text-left transition-colors ${statusFilter === s ? "border-white/25 bg-white/[0.04]" : "border-white/10 bg-white/[0.02] hover:border-white/15"}`}>
            <div className="text-2xl font-heading font-bold text-white">{counts[s]}</div>
            <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">{s === "all" ? "Total" : s}</div>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-white/30 animate-spin" />
        </div>
      ) : (
        <motion.div variants={containerVariants} initial="hidden" animate="show" className="space-y-3">
          {agents.map((agent) => (
            <AgentRow key={agent.id} agent={agent} onRefresh={fetchAgents} />
          ))}
        </motion.div>
      )}

      {!loading && agents.length === 0 && (
        <div className="border border-dashed border-white/10 bg-white/[0.02] flex flex-col items-center justify-center text-center py-20">
          <Plus className="w-8 h-8 text-white/25 mb-4" />
          <div className="text-xl font-heading uppercase tracking-widest text-white">No Agents</div>
          <p className="text-sm text-white/45 mt-3 max-w-sm">Create your first agent to get started.</p>
          <Link href="/dashboard/community-agents/create" className="mt-6">
            <div className="px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors cursor-pointer">Create Agent</div>
          </Link>
        </div>
      )}
    </div>
  );
}
