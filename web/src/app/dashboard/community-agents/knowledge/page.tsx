"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, Check, Clock, ExternalLink, FileText, Loader2, Plus, RefreshCcw, Trash2 } from "lucide-react";
import { deleteKnowledgeSource, getAgent, listAgents } from "@/lib/agent-api";
import type { KnowledgeSource } from "@/lib/agent-types";

type AgentSource = KnowledgeSource & { agentId: string; agentName: string };

export default function KnowledgePage() {
  const [sources, setSources] = useState<AgentSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const loadSources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { agents } = await listAgents();
      const details = await Promise.all(agents.map((agent) => getAgent(agent.id)));
      setSources(details.flatMap((detail) => detail.knowledgeSources.map((source) => ({
        ...source,
        agentId: detail.agent.id,
        agentName: detail.agent.name,
      }))));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load knowledge sources.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSources(); }, [loadSources]);

  async function removeSource(source: AgentSource) {
    if (!confirm(`Delete “${source.name}” from ${source.agentName}?`)) return;
    setDeleting(source.id);
    try {
      await deleteKnowledgeSource(source.agentId, source.id);
      await loadSources();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Could not delete the source.");
    } finally {
      setDeleting(null);
    }
  }

  const ready = sources.filter((source) => source.status === "ready").length;
  const processing = sources.filter((source) => !["ready", "failed"].includes(source.status)).length;
  const chunks = sources.reduce((total, source) => total + source.chunkCount, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">Knowledge Sources</h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">Live indexed content across your agents.</p>
        </div>
        <Link href="/dashboard/community-agents/my-agents" className="flex items-center gap-2 px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest">
          <Plus className="w-3.5 h-3.5" /> Choose Agent
        </Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          ["Total Sources", sources.length], ["Ready", ready], ["Indexed Chunks", chunks], ["Processing", processing],
        ].map(([label, value]) => (
          <div key={label} className="p-4 border border-white/10 bg-white/[0.02]">
            <div className="text-2xl font-heading font-bold text-white">{value}</div>
            <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {error && (
        <div className="border border-red-400/30 bg-red-400/[0.05] p-4 flex items-center justify-between gap-4">
          <p className="text-xs text-red-200">{error}</p>
          <button onClick={loadSources} className="text-[10px] font-bold uppercase tracking-widest text-white">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 text-white/30 animate-spin" /></div>
      ) : sources.length === 0 && !error ? (
        <div className="border border-dashed border-white/10 py-20 text-center">
          <BookOpen className="w-8 h-8 text-white/20 mx-auto mb-4" />
          <div className="text-xl font-heading uppercase tracking-widest text-white">No knowledge indexed</div>
          <p className="text-sm text-white/40 mt-2">Open an agent and upload PDF, TXT, or Markdown files.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => (
            <div key={source.id} className="border border-white/10 bg-white/[0.02] p-4 flex items-center gap-4">
              <FileText className="w-4 h-4 text-white/40 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-white uppercase tracking-wider truncate">{source.name}</div>
                <div className="text-xs text-white/40 mt-1">{source.agentName} · {source.fileCount} files · {source.chunkCount} chunks</div>
                {source.errorMessage && <div className="text-[10px] text-red-300 mt-1">{source.errorMessage}</div>}
              </div>
              <span className={`text-[9px] uppercase tracking-widest px-2 py-1 font-bold ${source.status === "ready" ? "bg-white text-black" : source.status === "failed" ? "bg-red-500/10 text-red-300" : "bg-white/10 text-white/60"}`}>
                {source.status === "ready" ? <Check className="w-3 h-3 inline mr-1" /> : <RefreshCcw className="w-3 h-3 inline mr-1" />}{source.status}
              </span>
              <span className="hidden lg:flex items-center gap-1 text-[10px] text-white/30"><Clock className="w-3 h-3" />{new Date(source.updatedAt).toLocaleDateString()}</span>
              <Link href={`/dashboard/community-agents/agent/${source.agentId}`} className="p-2 text-white/30 hover:text-white" title="Open agent"><ExternalLink className="w-4 h-4" /></Link>
              <button onClick={() => removeSource(source)} disabled={deleting === source.id} className="p-2 text-white/30 hover:text-red-300 disabled:opacity-30" title="Delete source">
                {deleting === source.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
