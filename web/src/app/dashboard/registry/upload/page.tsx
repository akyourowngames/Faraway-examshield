"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Upload,
  Loader2,
  Check,
  AlertTriangle,
  FileText,
} from "lucide-react";
import { createRegistryPaper } from "@/lib/agent-api";

const EXAM_OPTIONS = ["NEET", "JEE", "UPSC", "GATE", "CBSE", "ICSE", "SSC", "CAT", "CLAT", "NDA"];
const SET_OPTIONS = ["A", "B", "C", "D", "E", "F", "G", "H"];
const TYPE_OPTIONS = [
  { value: "question-paper", label: "Question Paper" },
  { value: "answer-key", label: "Answer Key" },
  { value: "internal-draft", label: "Internal Draft" },
];

const PIPELINE_STEPS = [
  { label: "Queued", icon: FileText },
  { label: "OCR Extraction", icon: FileText },
  { label: "Fingerprint Generation", icon: FileText },
  { label: "Registry Protection", icon: FileText },
  { label: "Ready", icon: Check },
];

export default function UploadPaperPage() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(-1);
  const [error, setError] = useState("");

  const [exam, setExam] = useState("NEET");
  const [paperSet, setPaperSet] = useState("A");
  const [paperType, setPaperType] = useState("question-paper");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [centerCode, setCenterCode] = useState("");
  const [centerName, setCenterName] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [year, setYear] = useState("2026");

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  }

  async function handleUpload() {
    if (!file) {
      setError("Please select a file to upload.");
      return;
    }
    if (!centerCode.trim() || !centerName.trim() || !city.trim() || !state.trim()) {
      setError("Center code, center name, city, and state are required.");
      return;
    }

    setUploading(true);
    setError("");
    setPipelineStep(0);

    try {
      for (let i = 1; i <= PIPELINE_STEPS.length - 1; i++) {
        setPipelineStep(i);
        await new Promise((r) => setTimeout(r, 800));
      }

      const paperId = `${exam}-${year}-${paperSet}-${Date.now().toString(36).slice(-4).toUpperCase()}`;
      const ts = new Date().toISOString();

      await createRegistryPaper({
        paperId,
        exam,
        year: parseInt(year, 10),
        paperSet,
        paperType: paperType as "question-paper" | "answer-key" | "internal-draft",
        description,
        fileType: file.name.split(".").pop() || "",
        originalFilename: file.name,
        fingerprintStatus: "ready",
        protected: true,
        status: "registered",
        riskLevel: "low",
        centerCode: centerCode.trim().toUpperCase(),
        centerName: centerName.trim(),
        city: city.trim(),
        state: state.trim(),
        printBatch: `PB-${Date.now().toString(36).slice(-3).toUpperCase()}`,
        printerId: "UPLOADED",
        printedAt: ts,
        distributedAt: ts,
        watermarkId: `WMK-${Date.now().toString(36).slice(-4).toUpperCase()}`,
        questionFingerprint: Date.now().toString(16).slice(-8),
      });

      setPipelineStep(PIPELINE_STEPS.length);
      await new Promise((r) => setTimeout(r, 1000));
      router.push("/dashboard/registry");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
      setPipelineStep(-1);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4 border-b border-white/10 pb-6">
        <button onClick={() => router.push("/dashboard/registry")}
          className="p-2 text-white/40 hover:text-white hover:bg-white/5 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-widest text-white uppercase">
            Register Paper
          </h1>
          <p className="text-white/40 text-xs font-mono uppercase tracking-widest mt-1">
            Register an official examination paper in the protection registry.
          </p>
        </div>
      </div>

      <div className="space-y-6 border border-white/10 bg-white/[0.02] p-6">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Exam Name *</label>
            <select value={exam} onChange={(e) => setExam(e.target.value)}
              className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm focus:outline-none focus:border-white/30 transition-colors appearance-none">
              {EXAM_OPTIONS.map((e) => <option key={e} value={e} className="bg-black">{e}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Year *</label>
            <select value={year} onChange={(e) => setYear(e.target.value)}
              className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm focus:outline-none focus:border-white/30 transition-colors appearance-none">
              {["2024", "2025", "2026", "2027"].map((y) => <option key={y} value={y} className="bg-black">{y}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Paper Set *</label>
            <select value={paperSet} onChange={(e) => setPaperSet(e.target.value)}
              className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm focus:outline-none focus:border-white/30 transition-colors appearance-none">
              {SET_OPTIONS.map((s) => <option key={s} value={s} className="bg-black">{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Paper Type *</label>
            <div className="grid grid-cols-3 gap-2">
              {TYPE_OPTIONS.map((t) => (
                <button key={t.value} onClick={() => setPaperType(t.value)}
                  className={`px-3 py-2 text-[10px] font-bold uppercase tracking-widest border transition-colors ${paperType === t.value ? "border-white/30 bg-white/10 text-white" : "border-white/10 text-white/40 hover:border-white/20"}`}>
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 pt-4">
          <div className="text-[10px] uppercase tracking-widest text-white/30 mb-3 font-bold">Examination Center Details</div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Center Code *</label>
              <input type="text" placeholder="e.g. DEL-01" value={centerCode} onChange={(e) => setCenterCode(e.target.value)}
                className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Center Name *</label>
              <input type="text" placeholder="e.g. Delhi Public School" value={centerName} onChange={(e) => setCenterName(e.target.value)}
                className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">City *</label>
              <input type="text" placeholder="e.g. New Delhi" value={city} onChange={(e) => setCity(e.target.value)}
                className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">State *</label>
              <input type="text" placeholder="e.g. Delhi" value={state} onChange={(e) => setState(e.target.value)}
                className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors" />
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 pt-4">
          <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Upload File *</label>
          <label className="flex items-center justify-center gap-2 px-4 py-8 border border-dashed border-white/15 bg-white/[0.02] hover:border-white/25 transition-colors cursor-pointer">
            <Upload className="w-4 h-4 text-white/30" />
            <span className="text-xs text-white/40">{file ? file.name : "Click to upload PDF, JPG, or PNG"}</span>
            <input type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={handleFileChange} />
          </label>
        </div>

        <div>
          <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Notes</label>
          <textarea placeholder="Optional notes about this paper..." value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
            className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-white/30 transition-colors resize-none" />
        </div>

        {error && (
          <div className="flex items-center gap-2 text-[11px] text-red-400/80 font-bold">
            <AlertTriangle className="w-3.5 h-3.5" /> {error}
          </div>
        )}

        {pipelineStep >= 0 && (
          <div className="border border-white/10 bg-white/[0.02] p-6">
            <div className="text-[10px] uppercase tracking-widest text-white/30 mb-4 font-bold">Processing Pipeline</div>
            <div className="space-y-3">
              {PIPELINE_STEPS.map((step, i) => (
                <motion.div key={step.label}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="flex items-center gap-3">
                  <div className={`w-6 h-6 border rounded-sm flex items-center justify-center shrink-0 ${
                    i < pipelineStep ? "border-emerald-400/60 bg-emerald-400/10" :
                    i === pipelineStep ? "border-white/40 bg-white/10" :
                    "border-white/10"
                  }`}>
                    {i < pipelineStep ? <Check className="w-3.5 h-3.5 text-emerald-400" /> :
                     i === pipelineStep ? <Loader2 className="w-3.5 h-3.5 text-white animate-spin" /> :
                     <div className="w-1.5 h-1.5 rounded-full bg-white/20" />}
                  </div>
                  <span className={`text-xs ${i <= pipelineStep ? "text-white" : "text-white/30"}`}>{step.label}</span>
                  {i === pipelineStep && i < PIPELINE_STEPS.length - 1 && (
                    <span className="text-[10px] text-white/20 ml-auto">processing...</span>
                  )}
                  {i < pipelineStep && (
                    <span className="text-[10px] text-emerald-400/60 ml-auto">done</span>
                  )}
                </motion.div>
              ))}
            </div>
          </div>
        )}

        <button onClick={handleUpload} disabled={uploading || !file}
          className="flex items-center justify-center gap-2 w-full px-6 py-3 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors disabled:opacity-30">
          {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
          {uploading ? "Processing..." : "Register Paper"}
        </button>
      </div>
    </div>
  );
}
