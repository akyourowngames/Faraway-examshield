import { describe, it, expect } from "vitest";
import {
  detectionPercent,
  formatAnalysisJobStatus,
  formatDetectionScore,
  formatEvidenceSource,
  formatEvidenceStatus,
  formatOcrStatus,
  isTextEvidence,
} from "@/lib/evidence-format";

describe("evidence-format", () => {
  describe("isTextEvidence", () => {
    it("treats text/plain as text evidence", () => {
      expect(isTextEvidence({ fileType: "text/plain" })).toBe(true);
    });

    it("treats other types as non-text", () => {
      expect(isTextEvidence({ fileType: "image/png" })).toBe(false);
    });

    it("handles null/undefined", () => {
      expect(isTextEvidence(null)).toBe(false);
      expect(isTextEvidence(undefined)).toBe(false);
    });
  });

  describe("formatDetectionScore", () => {
    it("formats a score/max pair", () => {
      expect(formatDetectionScore(7, 10)).toBe("7/10");
    });

    it("falls back to Pending when missing", () => {
      expect(formatDetectionScore(null, 10)).toBe("Pending");
      expect(formatDetectionScore(7, null)).toBe("Pending");
      expect(formatDetectionScore(7, undefined)).toBe("Pending");
    });
  });

  describe("detectionPercent", () => {
    it("computes a rounded percentage", () => {
      expect(detectionPercent(7, 10)).toBe(70);
      expect(detectionPercent(1, 3)).toBe(33);
    });

    it("returns null when incomplete", () => {
      expect(detectionPercent(null, 10)).toBeNull();
      expect(detectionPercent(7, null)).toBeNull();
    });
  });

  describe("status label formatters", () => {
    it("maps evidence statuses to human labels", () => {
      expect(formatEvidenceStatus("pending-analysis")).toBe("Pending Analysis");
      expect(formatEvidenceStatus("analysis-failed")).toBe("Analysis Failed");
    });

    it("maps OCR statuses to human labels", () => {
      expect(formatOcrStatus("not-started")).toBe("Not Started");
      expect(formatOcrStatus("not-applicable")).toBe("Not Applicable");
    });

    it("maps analysis job statuses to human labels", () => {
      expect(formatAnalysisJobStatus("queued")).toBe("Queued");
      expect(formatAnalysisJobStatus("processing")).toBe("Processing");
    });

    it("maps evidence sources to human labels", () => {
      expect(formatEvidenceSource("manual-upload")).toBe("Manual Upload");
      expect(formatEvidenceSource("telegram")).toBe("Telegram");
    });
  });
});
