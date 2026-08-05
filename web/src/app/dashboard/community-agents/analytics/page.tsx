"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BookOpen, Clock, Loader2, MessageSquare, Users } from "lucide-react";
import { getAgent, listAgents } from "@/lib/agent-api";
import type { AgentDetail } from "@/lib/agent-types";

export default function AnalyticsPage() {
  const [details, setDetails] = useState<AgentDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { agents } = await listAgents();
      setDetails(await Promise.all(agents.map((agent) => getAgent(agent.id))));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load analytics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const metrics = useMemo(() => {
    const conversations = details.reduce((sum, detail) => sum + detail.stats.totalConversations, 0);
    const chunks = details.reduce((sum, detail) => sum + detail.stats.totalChunks, 0);
    const weightedLatency = details.reduce((sum, detail) => sum + detail.stats.avgLatencyMs * detail.stats.totalConversations, 0);
    return {
      conversations,
      active: details.filter((detail) => detail.agent.status === "active").length,
      chunks,
      latency: conversations ? Math.round(weightedLatency / conversations) : 0,
    };
  }, [details]);

  const ordered = [...details].sort((a, b) => b.stats.totalConversations - a.stats.totalConversations);

  return (
    <div className="space-y-8">
      <div className="border-b border-white/10 pb-6">
        <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">Analytics</h1>
        <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">Live performance across your agents.</p>
      </div>

      {error && <div className="border border-red-400/30 bg-red-400/[0.05] p-4 flex justify-between"><span className="text-xs text-red-200">{error}</span><button onClick={load} className="text-[10px] uppercase tracking-widest">Retry</button></div>}
      {loading ? <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-white/30" /></div> : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              ["Total Conversations", metrics.conversations, MessageSquare],
              ["Active Agents", metrics.active, Users],
              ["Knowledge Chunks", metrics.chunks, BookOpen],
              ["Avg Response Time", `${metrics.latency}ms`, Clock],
            ].map(([label, value, Icon]) => {
              const MetricIcon = Icon as typeof Users;
              return <div key={String(label)} className="border border-white/10 bg-white/[0.02] p-5"><MetricIcon className="w-4 h-4 text-white/30 mb-4" /><div className="text-3xl font-heading font-bold text-white">{value as string | number}</div><div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">{String(label)}</div></div>;
            })}
          </div>
          <div className="border border-white/10 bg-white/[0.02] p-6">
            <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50 mb-5">Agent Performance</h2>
            {ordered.length === 0 ? <p className="text-sm text-white/40">No agents yet. Analytics will appear after you create and test an agent.</p> : (
              <div className="space-y-2">
                {ordered.map((detail) => (
                  <Link key={detail.agent.id} href={`/dashboard/community-agents/agent/${detail.agent.id}`} className="grid grid-cols-[1fr_auto_auto_auto] gap-5 items-center border border-white/5 p-4 hover:border-white/20">
                    <div><div className="text-xs font-bold uppercase tracking-wider text-white">{detail.agent.name}</div><div className="text-[10px] uppercase tracking-widest text-white/30 mt-1">{detail.agent.status}</div></div>
                    <div className="text-right"><div className="text-sm text-white">{detail.stats.totalConversations}</div><div className="text-[9px] uppercase text-white/30">Chats</div></div>
                    <div className="text-right"><div className="text-sm text-white">{detail.stats.totalChunks}</div><div className="text-[9px] uppercase text-white/30">Chunks</div></div>
                    <div className="text-right"><div className="text-sm text-white">{detail.stats.avgLatencyMs}ms</div><div className="text-[9px] uppercase text-white/30">Latency</div></div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
