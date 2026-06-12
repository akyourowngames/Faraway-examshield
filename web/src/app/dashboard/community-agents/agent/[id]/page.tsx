"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Settings,
  BookOpen,
  BarChart3,
  MessageCircle,
  Loader2,
  TestTube,
  Send,
  Clock,
  Copy,
  Trash2,
} from "lucide-react";
import { getAgent, testAgent, listConversations, updateAgent } from "@/lib/agent-api";
import type { AgentDetail, AgentConversation, AgentTestResult } from "@/lib/agent-types";

type Tab = "overview" | "knowledge" | "analytics" | "settings" | "telegram";

const TABS: { id: Tab; label: string; icon: typeof Settings }[] = [
  { id: "overview", label: "Overview", icon: Settings },
  { id: "knowledge", label: "Knowledge", icon: BookOpen },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "settings", label: "Settings", icon: Settings },
  { id: "telegram", label: "Telegram", icon: MessageCircle },
];

export default function AgentDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;
  const [tab, setTab] = useState<Tab>("overview");
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [conversations, setConversations] = useState<AgentConversation[]>([]);
  const [testQuestion, setTestQuestion] = useState("");
  const [testResult, setTestResult] = useState<AgentTestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const fetchDetail = useCallback(async () => {
    try {
      const data = await getAgent(agentId);
      setDetail(data);
    } catch {
      router.push("/dashboard/community-agents/my-agents");
    } finally {
      setLoading(false);
    }
  }, [agentId, router]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  useEffect(() => {
    if (tab === "analytics") {
      listConversations(agentId).then((data) => setConversations(data.conversations)).catch(() => {});
    }
  }, [tab, agentId]);

  async function handleTest() {
    if (!testQuestion.trim()) return;
    setTesting(true);
    try {
      const result = await testAgent(agentId, testQuestion);
      setTestResult(result);
      fetchDetail();
    } catch {
      setTestResult({ response: "Test failed.", latencyMs: 0, sources: [], model: "", provider: "" });
    } finally {
      setTesting(false);
    }
  }

  async function handleToggleStatus() {
    if (!detail) return;
    const newStatus = detail.agent.status === "active" ? "paused" : "active";
    try {
      await updateAgent(agentId, { status: newStatus });
      fetchDetail();
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-white/30 animate-spin" />
      </div>
    );
  }

  if (!detail) return null;
  const { agent, stats, knowledgeSources, llmConfig, telegramConfig } = detail;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push("/dashboard/community-agents/my-agents")}
            className="p-2 text-white/40 hover:text-white hover:bg-white/5 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="w-12 h-12 bg-white/10 border border-white/10 flex items-center justify-center">
            <span className="text-sm font-bold font-heading text-white">{agent.avatar || agent.name.slice(0, 2).toUpperCase()}</span>
          </div>
          <div>
            <h1 className="text-3xl font-heading font-bold tracking-widest text-white uppercase">{agent.name}</h1>
            <p className="text-white/40 text-xs font-mono uppercase tracking-widest mt-1">{agent.category}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleToggleStatus}
            className={`px-4 py-2 text-xs font-bold uppercase tracking-widest border transition-colors ${agent.status === "active" ? "border-white/30 bg-white/10 text-white hover:bg-white/20" : "border-white/15 bg-white/[0.03] text-white/60 hover:border-white/40"}`}>
            {agent.status === "active" ? "Pause" : "Activate"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0 border-b border-white/10">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`relative flex items-center gap-2 px-4 py-3 text-xs font-semibold uppercase tracking-widest transition-colors ${tab === t.id ? "text-white" : "text-white/40 hover:text-white/60"}`}>
              <Icon className="w-3.5 h-3.5" />
              {t.label}
              {tab === t.id && (
                <motion.div layoutId="agent-tab" className="absolute bottom-0 left-0 right-0 h-[2px] bg-white" transition={{ type: "spring", stiffness: 400, damping: 30 }} />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <motion.div key={tab} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
        {tab === "overview" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Status", value: agent.status },
                { label: "Conversations", value: stats.totalConversations },
                { label: "Knowledge Sources", value: stats.totalKnowledgeSources },
                { label: "Avg Latency", value: `${stats.avgLatencyMs}ms` },
              ].map((s) => (
                <div key={s.label} className="p-4 border border-white/10 bg-white/[0.02]">
                  <div className="text-2xl font-heading font-bold text-white capitalize">{s.value}</div>
                  <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">{s.label}</div>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="border border-white/10 bg-white/[0.02] p-6">
                <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50 mb-4">Agent Info</h3>
                <div className="space-y-2">
                  {[
                    ["Description", agent.description || "—"],
                    ["Model", agent.model],
                    ["Provider", llmConfig?.provider || "Not configured"],
                    ["Visibility", agent.visibility],
                    ["Response Style", agent.responseStyle],
                    ["Citations", agent.citationMode ? "Enabled" : "Disabled"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                      <span className="text-white/30 uppercase tracking-wider text-[10px]">{k}</span>
                      <span className="text-white/60 text-right max-w-[200px] truncate">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="border border-white/10 bg-white/[0.02] p-6">
                <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50 mb-4">Test Agent</h3>
                <div className="flex gap-2 mb-4">
                  <input type="text" placeholder="Ask a question..." value={testQuestion} onChange={(e) => setTestQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleTest()}
                    className="flex-1 px-4 py-2 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
                  <button onClick={handleTest} disabled={testing || !testQuestion.trim()}
                    className="px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors disabled:opacity-30 flex items-center gap-2">
                    {testing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                    Send
                  </button>
                </div>
                {testResult && (
                  <div className="border border-white/10 bg-white/[0.03] p-4 space-y-3">
                    <div className="text-xs text-white/60 leading-relaxed">{testResult.response}</div>
                    <div className="flex items-center gap-4 text-[10px] text-white/30">
                      <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {testResult.latencyMs}ms</span>
                      <span>{testResult.provider}/{testResult.model}</span>
                    </div>
                    {testResult.sources.length > 0 && (
                      <div className="border-t border-white/5 pt-3">
                        <div className="text-[9px] uppercase tracking-widest text-white/20 mb-2">Sources</div>
                        {testResult.sources.map((s, i) => (
                          <div key={i} className="text-[10px] text-white/40 mb-1 truncate">{s.content.slice(0, 120)}...</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === "knowledge" && (
          <div className="space-y-4">
            {knowledgeSources.length === 0 ? (
              <div className="border border-dashed border-white/10 bg-white/[0.02] flex flex-col items-center justify-center text-center py-20">
                <BookOpen className="w-8 h-8 text-white/25 mb-4" />
                <div className="text-xl font-heading uppercase tracking-widest text-white">No Knowledge Sources</div>
                <p className="text-sm text-white/45 mt-3 max-w-sm">Upload documents to build the agent&apos;s knowledge base.</p>
              </div>
            ) : (
              knowledgeSources.map((source) => (
                <div key={source.id} className="border border-white/10 bg-white/[0.02] p-4 flex items-center gap-4">
                  <BookOpen className="w-4 h-4 text-white/30" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold text-white uppercase tracking-wider">{source.name}</div>
                    <div className="text-xs text-white/40 mt-0.5">{source.fileCount} file(s) &middot; {source.chunkCount} chunks &middot; {source.totalChars.toLocaleString()} chars</div>
                  </div>
                  <span className={`text-[9px] uppercase tracking-widest px-2 py-0.5 font-bold ${source.status === "ready" ? "bg-white text-black" : source.status === "failed" ? "bg-red-500/10 text-red-400" : "bg-white/10 text-white/60"}`}>
                    {source.status}
                  </span>
                </div>
              ))
            )}
          </div>
        )}

        {tab === "analytics" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Total Conversations", value: stats.totalConversations },
                { label: "Knowledge Chunks", value: stats.totalChunks },
                { label: "Avg Latency", value: `${stats.avgLatencyMs}ms` },
                { label: "Knowledge Sources", value: stats.totalKnowledgeSources },
              ].map((m) => (
                <div key={m.label} className="p-4 border border-white/10 bg-white/[0.02]">
                  <div className="text-2xl font-heading font-bold text-white">{m.value}</div>
                  <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1">{m.label}</div>
                </div>
              ))}
            </div>
            <div className="border border-white/10 bg-white/[0.02] p-6">
              <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50 mb-4">Recent Conversations</h3>
              {conversations.length === 0 ? (
                <p className="text-xs text-white/30">No conversations yet.</p>
              ) : (
                <div className="space-y-3">
                  {conversations.slice(0, 20).map((conv) => (
                    <div key={conv.id} className="border border-white/5 p-3 hover:border-white/15 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-white truncate">Q: {conv.userMessage}</div>
                          <div className="text-xs text-white/40 mt-1 line-clamp-2">A: {conv.agentResponse}</div>
                        </div>
                        <span className="text-[10px] text-white/30 shrink-0 font-mono">{conv.latencyMs}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "settings" && (
          <div className="space-y-6">
            <div className="border border-white/10 bg-white/[0.02] p-6">
              <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50 mb-4">System Prompt</h3>
              <div className="text-xs text-white/50 font-mono whitespace-pre-wrap">{agent.systemPrompt || "No system prompt configured."}</div>
            </div>
            <div className="border border-white/10 bg-white/[0.02] p-6">
              <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50 mb-4">LLM Configuration</h3>
              {llmConfig ? (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                    <span className="text-white/30 uppercase tracking-wider text-[10px]">Provider</span>
                    <span className="text-white/60">{llmConfig.provider}</span>
                  </div>
                  <div className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                    <span className="text-white/30 uppercase tracking-wider text-[10px]">Model</span>
                    <span className="text-white/60">{llmConfig.model}</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-white/30">Not configured.</p>
              )}
            </div>
            <div className="border border-red-500/20 bg-red-500/[0.02] p-6">
              <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-red-400/60 mb-4">Danger Zone</h3>
              <button onClick={() => { if (confirm("Delete this agent?")) { updateAgent(agentId, { status: "failed" as never }); router.push("/dashboard/community-agents/my-agents"); } }}
                className="flex items-center gap-2 px-4 py-2 border border-red-500/30 text-red-400/60 text-[10px] font-bold uppercase tracking-widest hover:bg-red-500/10 transition-colors">
                <Trash2 className="w-3 h-3" /> Delete Agent
              </button>
            </div>
          </div>
        )}

        {tab === "telegram" && (
          <div className="space-y-6">
            <div className="border border-white/10 bg-white/[0.02] p-6">
              <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50 mb-4">Telegram Configuration</h3>
              {telegramConfig && telegramConfig.botToken ? (
                <div className="space-y-3">
                  <div className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                    <span className="text-white/30 uppercase tracking-wider text-[10px]">Bot Username</span>
                    <span className="text-white/60">{telegramConfig.botUsername || "Not set"}</span>
                  </div>
                  <div className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                    <span className="text-white/30 uppercase tracking-wider text-[10px]">Status</span>
                    <span className="text-white/60 capitalize">{telegramConfig.deploymentStatus}</span>
                  </div>
                  <div className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                    <span className="text-white/30 uppercase tracking-wider text-[10px]">Privacy Mode Disabled</span>
                    <span className="text-white/60">{telegramConfig.privacyModeDisabled ? "Yes" : "No"}</span>
                  </div>
                  <div className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                    <span className="text-white/30 uppercase tracking-wider text-[10px]">Added To Group</span>
                    <span className="text-white/60">{telegramConfig.addedToGroup ? "Yes" : "No"}</span>
                  </div>
                  <div className="flex justify-between text-xs py-1.5 border-b border-white/[0.04]">
                    <span className="text-white/30 uppercase tracking-wider text-[10px]">Promoted Admin</span>
                    <span className="text-white/60">{telegramConfig.promotedAdmin ? "Yes" : "No"}</span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <MessageCircle className="w-8 h-8 text-white/25 mx-auto mb-4" />
                  <p className="text-sm text-white/40">Telegram not configured for this agent.</p>
                  <Link href="/dashboard/community-agents/create" className="mt-4 inline-block">
                    <span className="text-xs text-white/40 hover:text-white/60 underline">Configure during creation</span>
                  </Link>
                </div>
              )}
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
