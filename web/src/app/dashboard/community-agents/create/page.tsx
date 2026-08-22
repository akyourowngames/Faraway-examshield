"use client";

import { useState } from "react";
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
  X,
} from "lucide-react";
import { createAgent, deleteAgent, validateLLMKey, upsertLLMConfig, upsertTelegramConfig, createKnowledgeSource, uploadKnowledgeFiles, testAgent, verifyBotToken } from "@/lib/agent-api";
import { useApiQuery } from "@/lib/use-api";
import type { LLMProviderInfo, LLMProvider, AgentCategory, ResponseStyle } from "@/lib/agent-types";
import { agentBasicsSchema, agentLlmSchema } from "@/lib/validation";

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

const FALLBACK_PROVIDERS: LLMProviderInfo[] = [
  { id: "openai", name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"], requiresKey: true, requiresEndpoint: false, groupedModels: null },
  { id: "anthropic", name: "Anthropic", models: ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"], requiresKey: true, requiresEndpoint: false, groupedModels: null },
  { id: "grok", name: "Grok (xAI)", models: ["grok-3", "grok-3-mini", "grok-2"], requiresKey: true, requiresEndpoint: false, groupedModels: null },
  { id: "groq", name: "Groq", models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"], requiresKey: true, requiresEndpoint: false, groupedModels: null },
  { id: "opencode", name: "OpenCode Zen", models: [
    "big-pickle", "deepseek-v4-flash-free", "mimo-v2.5-free",
    "north-mini-code-free", "nemotron-3-ultra-free",
    "deepseek-v4-flash", "deepseek-v4-pro",
    "minimax-m2.5", "minimax-m2.7", "glm-5", "glm-5.1",
    "kimi-k2.5", "kimi-k2.6", "grok-build-0.1",
    "qwen3.5-plus", "qwen3.6-plus", "qwen3.7-plus", "qwen3.7-max",
    "claude-haiku-4-5", "claude-sonnet-4", "claude-sonnet-4-5", "claude-sonnet-4-6",
    "claude-opus-4-1", "claude-opus-4-5", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
    "claude-fable-5",
    "gpt-5", "gpt-5-nano", "gpt-5.1", "gpt-5.1-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini",
    "gpt-5.2", "gpt-5.2-codex", "gpt-5.3-codex", "gpt-5.3-codex-spark",
    "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-pro",
    "gpt-5.5", "gpt-5.5-pro",
    "gemini-3-flash", "gemini-3.1-pro", "gemini-3.5-flash",
  ], requiresKey: true, requiresEndpoint: false, groupedModels: {
    "Free Models": ["big-pickle", "deepseek-v4-flash-free", "mimo-v2.5-free", "north-mini-code-free", "nemotron-3-ultra-free"],
    "DeepSeek": ["deepseek-v4-flash", "deepseek-v4-pro"],
    "MiniMax": ["minimax-m2.5", "minimax-m2.7"],
    "GLM": ["glm-5", "glm-5.1"],
    "Kimi": ["kimi-k2.5", "kimi-k2.6"],
    "Grok": ["grok-build-0.1"],
    "Qwen": ["qwen3.5-plus", "qwen3.6-plus", "qwen3.7-plus", "qwen3.7-max"],
    "Claude": ["claude-haiku-4-5", "claude-sonnet-4", "claude-sonnet-4-5", "claude-sonnet-4-6", "claude-opus-4-1", "claude-opus-4-5", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-fable-5"],
    "GPT": ["gpt-5", "gpt-5-nano", "gpt-5.1", "gpt-5.1-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5.2", "gpt-5.2-codex", "gpt-5.3-codex", "gpt-5.3-codex-spark", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-pro", "gpt-5.5", "gpt-5.5-pro"],
    "Gemini": ["gemini-3-flash", "gemini-3.1-pro", "gemini-3.5-flash"],
  }},
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
  const { data: providersData } = useApiQuery<{ providers: LLMProviderInfo[] }>("/llm/providers");
  const providers = providersData?.providers?.length ? providersData.providers : FALLBACK_PROVIDERS;
  const [selectedProvider, setSelectedProvider] = useState<LLMProvider>("openai");
  const [apiKey, setApiKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
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
  const [stepError, setStepError] = useState("");
  const [verifyingBot, setVerifyingBot] = useState(false);
  const [botVerified, setBotVerified] = useState(false);
  const [botVerifyInfo, setBotVerifyInfo] = useState<{ firstName?: string; canJoinGroups?: boolean; canReadAllGroupMessages?: boolean } | null>(null);

  const currentProvider = providers.find((p) => p.id === selectedProvider);
  const modelOptions = currentProvider?.models ?? [];
  const displayModel = selectedModel || modelOptions[0] || "";

  async function handleValidateKey() {
    if (!apiKey) return;
    setValidating(true);
    setProviderError("");
    try {
      const result = await validateLLMKey({
        provider: selectedProvider,
        apiKey,
        model: selectedModel || modelOptions[0] || "",
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

  function addKnowledgeFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setKnowledgeFiles((prev) => {
      const merged = [...prev];
      for (const file of Array.from(fileList)) {
        const duplicate = merged.some((f) => f.name === file.name && f.size === file.size);
        if (!duplicate) merged.push(file);
      }
      return merged;
    });
  }

  function removeKnowledgeFile(index: number) {
    setKnowledgeFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async function handleCreate() {
    if (!name.trim() || !apiKey.trim() || !displayModel || !keyValidated) {
      setError("Complete and validate the LLM configuration before creating the agent.");
      return;
    }
    setCreating(true);
    setError("");
    let pendingAgentId: string | null = null;
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
      pendingAgentId = agentId;
      setCreatedAgentId(agentId);

      // Save LLM config
      await upsertLLMConfig(agentId, {
        provider: selectedProvider,
        model: displayModel || modelOptions[0] || "gpt-4o",
        apiKey,
      });

      // Save Telegram config if provided
      if (botToken) {
        await upsertTelegramConfig(agentId, {
          botToken,
          botUsername: botUsername || "",
          botVerified,
          privacyModeDisabled: Boolean(botVerifyInfo?.canReadAllGroupMessages),
          addedToGroup: false,
          promotedAdmin: false,
          messageReadingEnabled: Boolean(botVerifyInfo?.canReadAllGroupMessages),
          webhookUrl: "",
          deploymentStatus: botVerified ? "connected" : "disconnected",
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
      if (pendingAgentId) {
        try {
          await deleteAgent(pendingAgentId);
          setCreatedAgentId(null);
        } catch {
          // Preserve the original setup error; the orphan can still be removed from My Agents.
        }
      }
      setError(e instanceof Error ? e.message : "Failed to create agent");
    } finally {
      setCreating(false);
    }
  }

  async function handleVerifyBot() {
    if (!botToken.trim()) return;
    setVerifyingBot(true);
    setStepError("");
    try {
      const result = await verifyBotToken(botToken.trim());
      if (result.valid) {
        setBotVerified(true);
        setBotUsername(result.botUsername || "");
        setBotVerifyInfo({
          firstName: result.botFirstName,
          canJoinGroups: result.canJoinGroups,
          canReadAllGroupMessages: result.canReadAllGroupMessages,
        });
      } else {
        setBotVerified(false);
        setStepError(result.error || "Invalid bot token");
      }
    } catch (e) {
      setBotVerified(false);
      setStepError(e instanceof Error ? e.message : "Verification failed");
    } finally {
      setVerifyingBot(false);
    }
  }

  function validateStep(): string {
    if (step === 0) {
      const result = agentBasicsSchema.safeParse({ name, description, category, visibility });
      if (!result.success) {
        return result.error.issues[0]?.message ?? "Agent name is required.";
      }
    }
    if (step === 1) {
      const result = agentLlmSchema.safeParse({ apiKey, model: displayModel });
      if (!result.success) {
        const message = result.error.issues[0]?.message;
        if (message?.includes("API key")) return "API key is required.";
        if (message?.includes("model")) return "Select a model.";
      }
      if (!keyValidated) return "Validate the API key before proceeding.";
    }
    if (step === 2) {
      if (botToken.trim() && !botVerified) return "Verify your bot token before proceeding.";
    }
    return "";
  }

  function next() {
    const error = validateStep();
    if (error) {
      setStepError(error);
      return;
    }
    setStepError("");
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
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">API Key</label>
                <input type="password" placeholder="sk-..." value={apiKey} onChange={(e) => { setApiKey(e.target.value); setKeyValidated(false); }}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors font-mono" />
              </div>
              {modelOptions.length > 0 && (
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Model</label>
                  {currentProvider?.groupedModels ? (
                    // Grouped dropdown for providers with many models (like OpenCode Zen)
                    <div className="space-y-3">
                      <div className="relative">
                        <select
                          value={selectedModel || ""}
                          onChange={(e) => {
                            if (e.target.value) {
                              setSelectedModel(e.target.value);
                              setKeyValidated(false);
                            }
                          }}
                          className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm focus:outline-none focus:border-white/30 transition-colors appearance-none cursor-pointer pr-10"
                          style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.4)' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center' }}
                        >
                          <option value="" className="bg-black text-white">Select a model...</option>
                          {Object.entries(currentProvider.groupedModels).map(([group, models]) => (
                            <optgroup key={group} label={group} className="bg-black text-white font-bold">
                              {models.map((m) => (
                                <option key={m} value={m} className="bg-black text-white font-normal">{m}</option>
                              ))}
                            </optgroup>
                          ))}
                        </select>
                      </div>
                      {selectedModel && (
                        <div className="flex items-center gap-2 px-3 py-2 border border-white/10 bg-white/[0.02]">
                          <div className="text-[10px] text-white/40 uppercase tracking-wider">Selected:</div>
                          <div className="text-xs font-bold text-white">{selectedModel}</div>
                        </div>
                      )}
                    </div>
                  ) : (
                    // Simple grid for providers with few models
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {modelOptions.map((m) => (
                        <button key={m} onClick={() => { setSelectedModel(m); setKeyValidated(false); }}
                          className={`px-4 py-3 border transition-colors text-left ${selectedModel === m ? "border-white/30 bg-white/10" : "border-white/10 hover:border-white/20"}`}>
                          <div className="text-xs font-bold text-white uppercase tracking-wider">{m}</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div className="flex items-center gap-3">
                <button onClick={handleValidateKey} disabled={validating || !apiKey}
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
                <div className="flex gap-2">
                  <input type="password" placeholder="123456:ABC-..." value={botToken} onChange={(e) => { setBotToken(e.target.value); setBotVerified(false); setBotVerifyInfo(null); }}
                    className="flex-1 px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors font-mono" />
                  <button onClick={handleVerifyBot} disabled={verifyingBot || !botToken.trim()}
                    className="flex items-center gap-2 px-4 py-3 bg-white/10 border border-white/15 text-white text-xs font-bold uppercase tracking-widest hover:bg-white/15 transition-colors disabled:opacity-30 shrink-0">
                    {verifyingBot ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                    {verifyingBot ? "Verifying..." : "Verify"}
                  </button>
                </div>
                {botVerified && (
                  <div className="mt-2 flex items-center gap-2 text-[11px] text-emerald-400/80 font-bold">
                    <Check className="w-3.5 h-3.5" />
                    Connected as @{botUsername} {botVerifyInfo?.firstName ? `(${botVerifyInfo.firstName})` : ""}
                  </div>
                )}
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Bot Username</label>
                <input type="text" placeholder="@your_bot_username" value={botUsername} onChange={(e) => setBotUsername(e.target.value)}
                  disabled={botVerified}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors disabled:opacity-40" />
              </div>
              <div className="border border-white/10 bg-white/[0.02] p-4">
                <div className="text-[10px] uppercase tracking-widest text-white/30 mb-3 font-bold">Setup Checklist</div>
                <div className="space-y-2 text-xs text-white/40">
                  {[
                    { label: "Disable Privacy Mode", done: botVerifyInfo?.canReadAllGroupMessages ?? false },
                    { label: "Add Bot To Group", done: false },
                    { label: "Promote To Admin", done: false },
                    { label: "Enable Message Reading", done: botVerifyInfo?.canReadAllGroupMessages ?? false },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-2">
                      <div className={`w-3.5 h-3.5 border rounded-sm flex items-center justify-center ${item.done ? "border-emerald-400/60 bg-emerald-400/10" : "border-white/20"}`}>
                        {item.done && <Check className="w-2.5 h-2.5 text-emerald-400" />}
                      </div>
                      <span className={item.done ? "text-emerald-400/60" : ""}>{item.label}</span>
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
                  {knowledgeFiles.length === 0 ? (
                    <label className="flex items-center justify-center gap-2 px-4 py-8 border border-dashed border-white/15 bg-white/[0.02] hover:border-white/25 transition-colors cursor-pointer">
                      <Upload className="w-4 h-4 text-white/30" />
                      <span className="text-xs text-white/40">Click to upload PDF, TXT, or Markdown</span>
                      <input type="file" multiple accept=".pdf,.txt,.md" className="hidden"
                        onChange={(e) => addKnowledgeFiles(e.target.files)} />
                    </label>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] uppercase tracking-widest text-white/40 font-bold">
                          {knowledgeFiles.length} file(s) selected
                        </span>
                        <div className="flex items-center gap-3">
                          <label className="text-[10px] uppercase tracking-widest text-white/50 hover:text-white cursor-pointer underline">
                            Add more
                            <input type="file" multiple accept=".pdf,.txt,.md" className="hidden"
                              onChange={(e) => addKnowledgeFiles(e.target.files)} />
                          </label>
                          <button type="button" onClick={() => setKnowledgeFiles([])}
                            className="text-[10px] uppercase tracking-widest text-red-300/70 hover:text-red-300 transition-colors">
                            Clear all
                          </button>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        {knowledgeFiles.map((file, index) => (
                          <div key={`${file.name}-${index}`} className="flex items-center gap-3 px-3 py-2 border border-white/10 bg-white/[0.02]">
                            <FileText className="w-4 h-4 text-white/30 shrink-0" />
                            <span className="flex-1 text-xs text-white/70 truncate">{file.name}</span>
                            <span className="text-[10px] text-white/30 shrink-0">{formatBytes(file.size)}</span>
                            <button type="button" onClick={() => removeKnowledgeFile(index)}
                              className="p-1 text-white/30 hover:text-red-300 transition-colors shrink-0" title="Remove file">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
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
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">Review & Create</h2>
              </div>
              {(() => {
                const checks = [
                  { label: "Agent Name", ok: !!name.trim(), critical: true },
                  { label: "LLM Provider", ok: !!selectedProvider, critical: true },
                  { label: "API Key", ok: !!apiKey.trim(), critical: true },
                  { label: "Model", ok: !!displayModel, critical: true },
                  { label: "Telegram Bot", ok: !botToken.trim() || botVerified, critical: false },
                  { label: "System Prompt", ok: !!systemPrompt.trim(), critical: false },
                  { label: "Knowledge Files", ok: knowledgeFiles.length > 0 || selectedKnowledgeTypes.length === 0, critical: false },
                ];
                const allCritical = checks.filter(c => c.critical).every(c => c.ok);
                return (
                  <>
                    <div className="border border-white/10 bg-white/[0.02] p-4">
                      <div className="text-[10px] uppercase tracking-widest text-white/30 mb-3 font-bold">Readiness</div>
                      <div className="space-y-2">
                        {checks.map((c) => (
                          <div key={c.label} className="flex items-center gap-2 text-xs">
                            <div className={`w-3.5 h-3.5 border rounded-sm flex items-center justify-center ${c.ok ? "border-emerald-400/60 bg-emerald-400/10" : c.critical ? "border-red-400/60 bg-red-400/10" : "border-white/20"}`}>
                              {c.ok && <Check className="w-2.5 h-2.5 text-emerald-400" />}
                              {!c.ok && c.critical && <AlertTriangle className="w-2.5 h-2.5 text-red-400" />}
                            </div>
                            <span className={c.ok ? "text-white/60" : c.critical ? "text-red-400/70" : "text-white/40"}>{c.label}</span>
                            <span className="ml-auto text-[10px] text-white/25">{c.ok ? "OK" : c.critical ? "Required" : "Optional"}</span>
                          </div>
                        ))}
                      </div>
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
                    {!allCritical && (
                      <div className="flex items-center gap-2 text-[11px] text-red-400/70 font-bold">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Complete required fields before deploying.
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Navigation */}
      <div className="space-y-3">
        {stepError && (
          <div className="flex items-center gap-2 text-[11px] text-red-400/80 font-bold">
            <AlertTriangle className="w-3.5 h-3.5" />
            {stepError}
          </div>
        )}
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
            <button onClick={handleCreate} disabled={creating || !name.trim() || !apiKey.trim() || !displayModel || !keyValidated}
              className="flex items-center gap-2 px-6 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors disabled:opacity-30">
              {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              {creating ? "Creating..." : "Create Agent"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
