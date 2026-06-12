"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Bot,
  Key,
  MessageCircle,
  BookOpen,
  Settings,
  Shield,
  Sparkles,
  Upload,
  FileText,
  Globe,
  Database,
  Loader2,
  AlertTriangle,
  Copy,
  ExternalLink,
  TestTube,
} from "lucide-react";
import { createAgent, listLLMProviders, validateLLMKey, upsertLLMConfig, upsertTelegramConfig, createKnowledgeSource, uploadKnowledgeFiles, testAgent } from "@/lib/agent-api";
import type { LLMProviderInfo, LLMProvider, AgentCategory, ResponseStyle } from "@/lib/agent-types";

const STEPS = ["Basics", "LLM Provider", "Telegram", "Knowledge", "Behavior", "Review"];

const CATEGORIES: { value: AgentCategory; label: string }[] = [
  { value: "education", label: "Education" },
  { value: "school-assistant", label: "School Assistant" },
  { value: "university-assistant", label: "University Assistant" },
  { value: "coaching-assistant", label: "Coaching Assistant" },
  { value: "security-assistant", label: "Security Assistant" },
  { value: "general", label: "General" },
];

const KNOWLEDGE_TYPES = [
  { icon: FileText, label: "Document", desc: "Upload PDF, TXT, or Markdown files", value: "document" },
  { icon: Globe, label: "URL", desc: "Import content from a web page", value: "url" },
];

export default function CreateAgentPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  // Step 1: Basics
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<AgentCategory>("general");
  const [visibility, setVisibility] = useState<"private" | "public">("private");

  // Step 2: LLM
  const [providers, setProviders] = useState<LLMProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<LLMProvider>("openai");
  const [apiKey, setApiKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [customEndpoint, setCustomEndpoint] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [keyValidated, setKeyValidated] = useState(false);
  const [validating, setValidating] = useState(false);
  const [providerError, setProviderError] = useState("");

  // Step 3: Telegram
  const [botToken, setBotToken] = useState("");
  const [botUsername, setBotUsername] = useState("");

  // Step 4: Knowledge
  const [selectedKnowledgeTypes, setSelectedKnowledgeTypes] = useState<string[]>([]);
  const [knowledgeFiles, setKnowledgeFiles] = useState<File[]>([]);

  // Step 5: Behavior
  const [systemPrompt, setSystemPrompt] = useState("");
  const [responseStyle, setResponseStyle] = useState<ResponseStyle>("balanced");
  const [citationMode, setCitationMode] = useState(true);
  const [testQuestion, setTestQuestion] = useState("");
  const [testResult, setTestResult] = useState<{ response: string; latencyMs: number; sources: Array<{ content: string; similarity: number }> } | null>(null);
  const [testing, setTesting] = useState(false);

  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null);

  useEffect(() => {
    listLLMProviders().then((data) => setProviders(data.providers)).catch(() => {});
  }, []);

  const currentProvider = providers.find((p) => p.id === selectedProvider);
  const modelOptions = selectedProvider === "custom" ? [] : currentProvider?.models ?? [];
  const displayModel = selectedProvider === "custom" ? customModel : selectedModel;

  async function handleValidateKey() {
    if (!apiKey && selectedProvider !== "custom") return;
    setValidating(true);
    setProviderError("");
    try {
      const result = await validateLLMKey({
        provider: selectedProvider,
        apiKey,
        model: selectedProvider === "custom" ? customModel : selectedModel || modelOptions[0] || "",
        endpointUrl: selectedProvider === "custom" ? customEndpoint : undefined,
      });
      if (result.valid) {
        setKeyValidated(true);
        if (result.model && !selectedModel) setSelectedModel(result.model);
      } else {
        setProviderError(result.error || "Invalid API key");
      }
    } catch (e) {
      setProviderError(e instanceof Error ? e.message : "Validation failed");
    } finally {
      setValidating(false);
    }
  }

  async function handleTestAgent() {
    if (!createdAgentId || !testQuestion.trim()) return;
    setTesting(true);
    try {
      const result = await testAgent(createdAgentId, testQuestion);
      setTestResult(result);
    } catch {
      setTestResult({ response: "Test failed. Please check your configuration.", latencyMs: 0, sources: [] });
    } finally {
      setTesting(false);
    }
  }

  async function handleCreate() {
    setCreating(true);
    setError("");
    try {
      const { agent } = await createAgent({
        name: name || "Untitled Agent",
        description,
        category,
        visibility,
        model: displayModel || "gpt-4o",
        systemPrompt,
        responseStyle,
        citationMode,
        tags: [category],
      });

      const agentId = agent.id;
      setCreatedAgentId(agentId);

      // Save LLM config
      await upsertLLMConfig(agentId, {
        provider: selectedProvider,
        model: displayModel || modelOptions[0] || "gpt-4o",
        apiKey,
        endpointUrl: selectedProvider === "custom" ? customEndpoint : undefined,
      });

      // Save Telegram config if provided
      if (botToken) {
        await upsertTelegramConfig(agentId, {
          botToken,
          botUsername: botUsername || "",
          botVerified: false,
          privacyModeDisabled: false,
          addedToGroup: false,
          promotedAdmin: false,
          messageReadingEnabled: false,
          webhookUrl: "",
          deploymentStatus: "disconnected",
        });
      }

      // Upload knowledge files if provided
      if (knowledgeFiles.length > 0 && selectedKnowledgeTypes.includes("document")) {
        const { source } = await createKnowledgeSource(agentId, {
          name: "Uploaded Documents",
          sourceType: "document",
          fileCount: knowledgeFiles.length,
        });
        await uploadKnowledgeFiles(agentId, source.id, knowledgeFiles);
      }

      router.push(`/dashboard/community-agents/my-agents`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create agent");
    } finally {
      setCreating(false);
    }
  }

  function next() {
    if (step < STEPS.length - 1) setStep(step + 1);
  }
  function prev() {
    if (step > 0) setStep(step - 1);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">
            Create Agent
          </h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">
            Build and deploy an AI agent step by step.
          </p>
        </div>
        <Link href="/dashboard/community-agents/discover">
          <div className="flex items-center gap-2 px-4 py-2 border border-white/15 bg-white/[0.03] text-white/60 text-xs font-bold uppercase tracking-widest hover:border-white/40 hover:text-white transition-colors cursor-pointer">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </div>
        </Link>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center gap-0">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center flex-1">
            <div className="flex items-center gap-2">
              <div
                className={`w-7 h-7 flex items-center justify-center text-[10px] font-bold border transition-colors ${
                  i < step
                    ? "bg-white text-black border-white"
                    : i === step
                    ? "bg-white/10 text-white border-white/30"
                    : "bg-transparent text-white/30 border-white/10"
                }`}
              >
                {i < step ? <Check className="w-3.5 h-3.5" /> : i + 1}
              </div>
              <span className={`text-[10px] uppercase tracking-widest font-bold hidden sm:inline ${i <= step ? "text-white" : "text-white/30"}`}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="flex-1 mx-3 h-[1px] bg-white/10">
                <div className="h-full bg-white transition-all duration-500" style={{ width: i < step ? "100%" : "0%" }} />
              </div>
            )}
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 border border-red-500/30 bg-red-500/10 text-red-400 text-xs">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Step Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
          className="border border-white/10 bg-white/[0.02] p-6 lg:p-8"
        >
          {step === 0 && (
            <div className="space-y-6">
              <div className="flex items-center gap-3 mb-6">
                <Bot className="w-5 h-5 text-white/50" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Agent Basics</h2>
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Agent Name</label>
                <input type="text" placeholder="e.g. School Assistant" value={name} onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Description</label>
                <textarea placeholder="What does this agent do?" value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors resize-none" />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Category</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {CATEGORIES.map((c) => (
                    <button key={c.value} onClick={() => setCategory(c.value)}
                      className={`px-4 py-3 text-xs font-bold uppercase tracking-widest border transition-colors text-left ${category === c.value ? "border-white/30 bg-white/10 text-white" : "border-white/10 text-white/40 hover:border-white/20 hover:text-white/60"}`}>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Visibility</label>
                <div className="grid grid-cols-2 gap-2">
                  {(["private", "public"] as const).map((v) => (
                    <button key={v} onClick={() => setVisibility(v)}
                      className={`px-4 py-3 text-xs font-bold uppercase tracking-widest border transition-colors ${visibility === v ? "border-white/30 bg-white/10 text-white" : "border-white/10 text-white/40 hover:border-white/20"}`}>
                      {v === "private" ? "Private" : "Public Marketplace"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-6">
              <div className="flex items-center gap-3 mb-6">
                <Key className="w-5 h-5 text-white/50" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">LLM Provider Configuration</h2>
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Provider</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {providers.map((p) => (
                    <button key={p.id} onClick={() => { setSelectedProvider(p.id as LLMProvider); setKeyValidated(false); setApiKey(""); setSelectedModel(""); }}
                      className={`px-3 py-3 text-xs font-bold uppercase tracking-widest border transition-colors text-left ${selectedProvider === p.id ? "border-white/30 bg-white/10 text-white" : "border-white/10 text-white/40 hover:border-white/20"}`}>
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>
              {selectedProvider !== "custom" && (
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">API Key</label>
                  <input type="password" placeholder="sk-..." value={apiKey} onChange={(e) => { setApiKey(e.target.value); setKeyValidated(false); }}
                    className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors font-mono" />
                </div>
              )}
              {selectedProvider === "custom" && (
                <>
                  <div>
                    <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Endpoint URL</label>
                    <input type="text" placeholder="https://your-api.com/v1/chat/completions" value={customEndpoint} onChange={(e) => setCustomEndpoint(e.target.value)}
                      className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors font-mono" />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">API Key</label>
                    <input type="password" placeholder="your-api-key" value={apiKey} onChange={(e) => { setApiKey(e.target.value); setKeyValidated(false); }}
                      className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors font-mono" />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Model Name</label>
                    <input type="text" placeholder="e.g. gpt-4o" value={customModel} onChange={(e) => setCustomModel(e.target.value)}
                      className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors font-mono" />
                  </div>
                </>
              )}
              {modelOptions.length > 0 && (
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Model</label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {modelOptions.map((m) => (
                      <button key={m} onClick={() => { setSelectedModel(m); setKeyValidated(false); }}
                        className={`px-4 py-3 border transition-colors text-left ${selectedModel === m ? "border-white/30 bg-white/10" : "border-white/10 hover:border-white/20"}`}>
                        <div className="text-xs font-bold text-white uppercase tracking-wider">{m}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex items-center gap-3">
                <button onClick={handleValidateKey} disabled={validating || (!apiKey && selectedProvider !== "custom")}
                  className="flex items-center gap-2 px-4 py-2 border border-white/15 bg-white/[0.03] text-white/60 text-xs font-bold uppercase tracking-widest hover:border-white/40 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                  {validating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
                  Validate Key
                </button>
                {keyValidated && (
                  <span className="flex items-center gap-1.5 text-[10px] text-emerald-400/80 font-bold uppercase tracking-widest">
                    <Check className="w-3.5 h-3.5" /> Key Valid
                  </span>
                )}
                {providerError && (
                  <span className="text-[10px] text-red-400/80 font-bold">{providerError}</span>
                )}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              <div className="flex items-center gap-3 mb-6">
                <MessageCircle className="w-5 h-5 text-white/50" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Telegram Deployment</h2>
              </div>
              <p className="text-xs text-white/40">Connect a Telegram bot to deploy your agent. You can skip this and configure later.</p>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Bot Token</label>
                <input type="password" placeholder="123456:ABC-..." value={botToken} onChange={(e) => setBotToken(e.target.value)}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors font-mono" />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Bot Username</label>
                <input type="text" placeholder="@your_bot_username" value={botUsername} onChange={(e) => setBotUsername(e.target.value)}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
              </div>
              <div className="border border-white/10 bg-white/[0.02] p-4">
                <div className="text-[10px] uppercase tracking-widest text-white/30 mb-3 font-bold">Setup Checklist</div>
                <div className="space-y-2 text-xs text-white/40">
                  {["Disable Privacy Mode", "Add Bot To Group", "Promote To Admin", "Enable Message Reading"].map((item) => (
                    <div key={item} className="flex items-center gap-2">
                      <div className="w-3.5 h-3.5 border border-white/20 rounded-sm" />
                      {item}
                    </div>
                  ))}
                </div>
              </div>
              <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-xs text-white/40 hover:text-white/60 transition-colors">
                <ExternalLink className="w-3 h-3" /> Create a bot with BotFather
              </a>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6">
              <div className="flex items-center gap-3 mb-6">
                <BookOpen className="w-5 h-5 text-white/50" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Knowledge Sources</h2>
              </div>
              <p className="text-xs text-white/40">Select knowledge types and upload files. This builds the agent&apos;s RAG knowledge base.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {KNOWLEDGE_TYPES.map((kt) => {
                  const Icon = kt.icon;
                  const isSelected = selectedKnowledgeTypes.includes(kt.value);
                  return (
                    <button key={kt.value}
                      onClick={() => setSelectedKnowledgeTypes((prev) => isSelected ? prev.filter((x) => x !== kt.value) : [...prev, kt.value])}
                      className={`flex items-center gap-4 px-5 py-4 border transition-colors text-left ${isSelected ? "border-white/30 bg-white/[0.05]" : "border-white/10 bg-white/[0.02] hover:border-white/20"}`}>
                      <Icon className={`w-5 h-5 ${isSelected ? "text-white" : "text-white/30"}`} />
                      <div>
                        <div className="text-xs font-bold text-white uppercase tracking-wider">{kt.label}</div>
                        <div className="text-[10px] text-white/40 mt-0.5">{kt.desc}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
              {selectedKnowledgeTypes.includes("document") && (
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Upload Files</label>
                  <label className="flex items-center justify-center gap-2 px-4 py-8 border border-dashed border-white/15 bg-white/[0.02] hover:border-white/25 transition-colors cursor-pointer">
                    <Upload className="w-4 h-4 text-white/30" />
                    <span className="text-xs text-white/40">{knowledgeFiles.length > 0 ? `${knowledgeFiles.length} file(s) selected` : "Click to upload PDF, TXT, or Markdown"}</span>
                    <input type="file" multiple accept=".pdf,.txt,.md" className="hidden"
                      onChange={(e) => setKnowledgeFiles(Array.from(e.target.files || []))} />
                  </label>
                </div>
              )}
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6">
              <div className="flex items-center gap-3 mb-6">
                <Settings className="w-5 h-5 text-white/50" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Agent Behavior</h2>
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">System Prompt</label>
                <textarea placeholder="You are a helpful school assistant. Answer only using provided knowledge."
                  value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={6}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors resize-none font-mono" />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Response Style</label>
                <div className="grid grid-cols-3 gap-2">
                  {(["short", "balanced", "detailed"] as const).map((s) => (
                    <button key={s} onClick={() => setResponseStyle(s)}
                      className={`px-4 py-3 text-xs font-bold uppercase tracking-widest border transition-colors ${responseStyle === s ? "border-white/30 bg-white/10 text-white" : "border-white/10 text-white/40 hover:border-white/20"}`}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between py-3 border-b border-white/5">
                <div>
                  <div className="text-xs font-bold text-white uppercase tracking-wider">Citation Mode</div>
                  <div className="text-[10px] text-white/40 mt-0.5">Show source document references in responses</div>
                </div>
                <button onClick={() => setCitationMode(!citationMode)}
                  className={`w-10 h-5 rounded-full transition-colors relative ${citationMode ? "bg-white" : "bg-white/20"}`}>
                  <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-transform ${citationMode ? "left-5 bg-black" : "left-0.5 bg-white/60"}`} />
                </button>
              </div>
              {createdAgentId && (
                <div className="border border-white/10 bg-white/[0.02] p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <TestTube className="w-4 h-4 text-white/50" />
                    <span className="text-xs font-bold uppercase tracking-widest text-white">Test Agent</span>
                  </div>
                  <div className="flex gap-2">
                    <input type="text" placeholder="Ask a question..." value={testQuestion} onChange={(e) => setTestQuestion(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleTestAgent()}
                      className="flex-1 px-4 py-2 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
                    <button onClick={handleTestAgent} disabled={testing || !testQuestion.trim()}
                      className="px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors disabled:opacity-30">
                      {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Test"}
                    </button>
                  </div>
                  {testResult && (
                    <div className="border border-white/10 bg-white/[0.03] p-3 space-y-2">
                      <div className="text-xs text-white/60">{testResult.response}</div>
                      {testResult.latencyMs > 0 && (
                        <div className="text-[10px] text-white/30">Latency: {testResult.latencyMs}ms</div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {step === 5 && (
            <div className="space-y-6">
              <div className="flex items-center gap-3 mb-6">
                <Shield className="w-5 h-5 text-white/50" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Review & Deploy</h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  { label: "Name", value: name || "Untitled Agent" },
                  { label: "Category", value: category },
                  { label: "Visibility", value: visibility },
                  { label: "Provider", value: selectedProvider },
                  { label: "Model", value: displayModel || "Not set" },
                  { label: "Telegram", value: botUsername || "Not configured" },
                  { label: "Knowledge", value: `${knowledgeFiles.length} file(s)` },
                  { label: "Response Style", value: responseStyle },
                  { label: "Citations", value: citationMode ? "Enabled" : "Disabled" },
                ].map((item) => (
                  <div key={item.label} className="border border-white/10 bg-white/[0.02] p-4">
                    <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">{item.label}</div>
                    <div className="text-sm text-white font-bold capitalize">{item.value}</div>
                  </div>
                ))}
              </div>
              {systemPrompt && (
                <div className="border border-white/10 bg-white/[0.02] p-4">
                  <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">System Prompt</div>
                  <div className="text-xs text-white/60 font-mono max-h-32 overflow-y-auto">{systemPrompt}</div>
                </div>
              )}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button onClick={prev} disabled={step === 0}
          className="flex items-center gap-2 px-4 py-2 border border-white/15 bg-white/[0.03] text-white/60 text-xs font-bold uppercase tracking-widest hover:border-white/40 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
          <ArrowLeft className="w-3.5 h-3.5" /> Previous
        </button>
        {step < STEPS.length - 1 ? (
          <button onClick={next}
            className="flex items-center gap-2 px-6 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors">
            Next <ArrowRight className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button onClick={handleCreate} disabled={creating}
            className="flex items-center gap-2 px-6 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors disabled:opacity-50">
            {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {creating ? "Creating..." : "Create Agent"}
          </button>
        )}
      </div>
    </div>
  );
}
