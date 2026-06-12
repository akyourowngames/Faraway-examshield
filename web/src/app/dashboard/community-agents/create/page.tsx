"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Bot,
  BookOpen,
  Shield,
  Settings,
  Sparkles,
  Upload,
  Globe,
  Database,
  FileText,
} from "lucide-react";
import Link from "next/link";

const STEPS = ["Basics", "Knowledge", "Behavior", "Review"];

const CATEGORY_OPTIONS = [
  { value: "security", label: "Security" },
  { value: "forensics", label: "Forensics" },
  { value: "compliance", label: "Compliance" },
  { value: "investigation", label: "Investigation" },
  { value: "monitoring", label: "Monitoring" },
  { value: "general", label: "General" },
];

const MODEL_OPTIONS = [
  { value: "gpt-4o", label: "GPT-4o", desc: "Most capable, best for complex reasoning" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini", desc: "Fast and efficient for standard tasks" },
];

const KNOWLEDGE_TYPES = [
  { icon: FileText, label: "Document", desc: "Upload PDF, TXT, or Markdown files" },
  { icon: Globe, label: "URL", desc: "Import content from a web page" },
  { icon: Database, label: "Database", desc: "Connect to a data source" },
  { icon: Upload, label: "API", desc: "Link an external API endpoint" },
];

export default function CreateAgentPage() {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("security");
  const [model, setModel] = useState("gpt-4o");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [selectedKnowledgeTypes, setSelectedKnowledgeTypes] = useState<string[]>([]);

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
            Build a new AI agent step by step.
          </p>
        </div>
        <Link href="/dashboard/community-agents/discover">
          <div className="flex items-center gap-2 px-4 py-2 border border-white/15 bg-white/[0.03] text-white/60 text-xs font-bold uppercase tracking-widest hover:border-white/40 hover:text-white transition-colors cursor-pointer">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Marketplace
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
              <span
                className={`text-[10px] uppercase tracking-widest font-bold hidden sm:inline ${
                  i <= step ? "text-white" : "text-white/30"
                }`}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="flex-1 mx-3 h-[1px] bg-white/10">
                <div
                  className="h-full bg-white transition-all duration-500"
                  style={{ width: i < step ? "100%" : "0%" }}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <motion.div
        key={step}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
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
              <input
                type="text"
                placeholder="e.g. Threat Scanner"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Description</label>
              <textarea
                placeholder="What does this agent do?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors resize-none"
              />
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Category</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {CATEGORY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setCategory(opt.value)}
                    className={`px-4 py-3 text-xs font-bold uppercase tracking-widest border transition-colors text-left ${
                      category === opt.value
                        ? "border-white/30 bg-white/10 text-white"
                        : "border-white/10 text-white/40 hover:border-white/20 hover:text-white/60"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Model</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {MODEL_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setModel(opt.value)}
                    className={`px-4 py-3 border transition-colors text-left ${
                      model === opt.value
                        ? "border-white/30 bg-white/10"
                        : "border-white/10 hover:border-white/20"
                    }`}
                  >
                    <div className="text-xs font-bold text-white uppercase tracking-wider">{opt.label}</div>
                    <div className="text-[10px] text-white/40 mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 mb-6">
              <BookOpen className="w-5 h-5 text-white/50" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-white">Knowledge Sources</h2>
            </div>
            <p className="text-xs text-white/40">Select the types of knowledge this agent will have access to.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {KNOWLEDGE_TYPES.map((kt) => {
                const Icon = kt.icon;
                const isSelected = selectedKnowledgeTypes.includes(kt.label);
                return (
                  <button
                    key={kt.label}
                    onClick={() =>
                      setSelectedKnowledgeTypes((prev) =>
                        isSelected ? prev.filter((x) => x !== kt.label) : [...prev, kt.label]
                      )
                    }
                    className={`flex items-center gap-4 px-5 py-4 border transition-colors text-left ${
                      isSelected
                        ? "border-white/30 bg-white/[0.05]"
                        : "border-white/10 bg-white/[0.02] hover:border-white/20"
                    }`}
                  >
                    <Icon className={`w-5 h-5 ${isSelected ? "text-white" : "text-white/30"}`} />
                    <div>
                      <div className="text-xs font-bold text-white uppercase tracking-wider">{kt.label}</div>
                      <div className="text-[10px] text-white/40 mt-0.5">{kt.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 mb-6">
              <Settings className="w-5 h-5 text-white/50" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-white">Agent Behavior</h2>
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">System Prompt</label>
              <textarea
                placeholder="Define how this agent should behave, what it should focus on, and any constraints..."
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={8}
                className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors resize-none font-mono"
              />
              <p className="text-[10px] text-white/30 mt-2">
                The system prompt defines the agent&apos;s personality, expertise, and response guidelines.
              </p>
            </div>

            <div className="border border-white/10 bg-white/[0.02] p-4">
              <div className="text-[10px] uppercase tracking-widest text-white/30 mb-2 font-bold">Preview</div>
              <div className="text-xs text-white/50 font-mono">
                {systemPrompt || "No system prompt defined. The agent will use default behavior."}
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 mb-6">
              <Shield className="w-5 h-5 text-white/50" />
              <h2 className="text-sm font-bold uppercase tracking-widest text-white">Review & Create</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="border border-white/10 bg-white/[0.02] p-4">
                <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">Name</div>
                <div className="text-sm text-white font-bold">{name || "Untitled Agent"}</div>
              </div>
              <div className="border border-white/10 bg-white/[0.02] p-4">
                <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">Category</div>
                <div className="text-sm text-white font-bold capitalize">{category}</div>
              </div>
              <div className="border border-white/10 bg-white/[0.02] p-4">
                <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">Model</div>
                <div className="text-sm text-white font-bold">{model}</div>
              </div>
              <div className="border border-white/10 bg-white/[0.02] p-4">
                <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">Knowledge Sources</div>
                <div className="text-sm text-white font-bold">{selectedKnowledgeTypes.length || "None"} selected</div>
              </div>
            </div>

            <div className="border border-white/10 bg-white/[0.02] p-4">
              <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">Description</div>
              <div className="text-xs text-white/60">{description || "No description provided."}</div>
            </div>

            <div className="border border-white/10 bg-white/[0.02] p-4">
              <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">System Prompt</div>
              <div className="text-xs text-white/60 font-mono max-h-32 overflow-y-auto">{systemPrompt || "Default behavior."}</div>
            </div>
          </div>
        )}
      </motion.div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={prev}
          disabled={step === 0}
          className="flex items-center gap-2 px-4 py-2 border border-white/15 bg-white/[0.03] text-white/60 text-xs font-bold uppercase tracking-widest hover:border-white/40 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Previous
        </button>
        {step < STEPS.length - 1 ? (
          <button
            onClick={next}
            className="flex items-center gap-2 px-6 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors"
          >
            Next
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button className="flex items-center gap-2 px-6 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors">
            <Sparkles className="w-3.5 h-3.5" />
            Create Agent
          </button>
        )}
      </div>
    </div>
  );
}
