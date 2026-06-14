"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Loader2,
  Shield,
  AlertTriangle,
  FileText,
  MapPin,
  Clock,
  Trash2,
  Eye,
} from "lucide-react";
import { getRegistryPaper, deleteRegistryPaper } from "@/lib/agent-api";
import type { RegistryPaper } from "@/lib/agent-types";

const STATUS_COLORS: Record<string, string> = {
  registered: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
  received: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  in_transit: "bg-amber-500/10 text-amber-400 border border-amber-500/20",
  investigating: "bg-orange-500/10 text-orange-400 border border-orange-500/20",
  compromised: "bg-red-500/10 text-red-400 border border-red-500/20",
};

const RISK_COLORS: Record<string, string> = {
  low: "text-emerald-400",
  medium: "text-amber-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

export default function PaperDetailPage() {
  const params = useParams();
  const router = useRouter();
  const paperId = params.paperId as string;
  const [paper, setPaper] = useState<RegistryPaper | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);

  const fetchPaper = useCallback(async () => {
    try {
      const data = await getRegistryPaper(paperId);
      setPaper(data.paper);
    } catch {
      router.push("/dashboard/registry");
    } finally {
      setLoading(false);
    }
  }, [paperId, router]);

  useEffect(() => { fetchPaper(); }, [fetchPaper]);

  async function handleDelete() {
    if (!confirm(`Delete paper ${paperId}?`)) return;
    setDeleting(true);
    try {
      await deleteRegistryPaper(paperId);
      router.push("/dashboard/registry");
    } catch {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-white/30 animate-spin" />
      </div>
    );
  }

  if (!paper) return null;

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between border-b border-white/10 pb-6">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push("/dashboard/registry")}
            className="p-2 text-white/40 hover:text-white hover:bg-white/5 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-3xl font-heading font-bold tracking-widest text-white uppercase font-mono">{paper.paperId}</h1>
            <p className="text-white/40 text-xs font-mono uppercase tracking-widest mt-1">
              {paper.exam} {paper.year} &middot; Set {paper.paperSet}
            </p>
          </div>
        </div>
        <button onClick={handleDelete} disabled={deleting}
          className="flex items-center gap-2 px-3 py-2 border border-red-500/20 text-red-400/60 text-xs font-bold uppercase tracking-widest hover:bg-red-500/10 transition-colors disabled:opacity-30">
          {deleting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />} Delete
        </button>
      </div>

      {/* Status badges */}
      <div className="flex items-center gap-3">
        <span className={`text-[10px] uppercase tracking-widest px-3 py-1 font-bold rounded-sm ${STATUS_COLORS[paper.status] || "bg-white/10 text-white/60"}`}>
          {paper.status.replace("_", " ")}
        </span>
        <span className={`text-[10px] uppercase tracking-widest px-3 py-1 font-bold border border-white/10 ${RISK_COLORS[paper.riskLevel] || "text-white/40"}`}>
          {paper.riskLevel} risk
        </span>
        {paper.protected && (
          <span className="flex items-center gap-1 text-[10px] uppercase tracking-widest px-3 py-1 font-bold text-emerald-400/80 border border-emerald-400/20">
            <Shield className="w-3 h-3" /> Protected
          </span>
        )}
      </div>

      {/* Paper Intelligence */}
      <div className="grid grid-cols-2 gap-4">
        {[
          { label: "Exam", value: paper.exam },
          { label: "Year", value: paper.year },
          { label: "Paper Set", value: paper.paperSet },
          { label: "Paper Type", value: paper.paperType?.replace("-", " ") || "Question Paper" },
          { label: "Upload Date", value: paper.uploadedAt ? new Date(paper.uploadedAt).toLocaleDateString() : "N/A" },
          { label: "Fingerprint", value: paper.questionFingerprint || "N/A" },
          { label: "Fingerprint Status", value: paper.fingerprintStatus },
          { label: "OCR Confidence", value: `${paper.ocrConfidence || 0}%` },
          { label: "Total Questions", value: paper.totalQuestions || 0 },
          { label: "Watermark ID", value: paper.watermarkId },
          { label: "Center Code", value: paper.centerCode },
          { label: "Center Name", value: paper.centerName },
          { label: "City", value: paper.city },
          { label: "State", value: paper.state },
          { label: "Print Batch", value: paper.printBatch },
          { label: "Printer ID", value: paper.printerId },
        ].map((item) => (
          <div key={item.label} className="border border-white/10 bg-white/[0.02] p-4">
            <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">{item.label}</div>
            <div className="text-sm text-white font-bold">{item.value}</div>
          </div>
        ))}
      </div>

      {paper.description && (
        <div className="border border-white/10 bg-white/[0.02] p-4">
          <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">Description</div>
          <div className="text-xs text-white/60">{paper.description}</div>
        </div>
      )}

      {paper.originalFilename && (
        <div className="border border-white/10 bg-white/[0.02] p-4 flex items-center gap-3">
          <FileText className="w-4 h-4 text-white/30" />
          <div>
            <div className="text-xs text-white/60">{paper.originalFilename}</div>
            <div className="text-[10px] text-white/30 uppercase">{paper.fileType}</div>
          </div>
        </div>
      )}
    </div>
  );
}
