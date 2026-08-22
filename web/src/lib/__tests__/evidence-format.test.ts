import { describe, expect, it } from "vitest";
import {
  detectionPercent,
  formatAnalysisJobStatus,
  formatDetectionScore,
  formatEvidenceSource,
  formatEvidenceStatus,
  formatEvidenceDateTime,
  formatOcrStatus,
  isTextEvidence,
} from "@/lib/evidence-format";

describe("isTextEvidence", () => {
  it("detects text/plain evidence", () => {
    expect(isTextEvidence({ fileType: "text/plain" })).toBe(true);
    expect(isTextEvidence({ fileType: "image/jpeg" })).toBe(false);
  });

  it("treats missing evidence as non-text", () => {
    expect(isTextEvidence(null)).toBe(false);
    expect(isTextEvidence(undefined)).toBe(false);
  });
});

describe("formatDetectionScore", () => {
  it("formats score over max", () => {
    expect(formatDetectionScore(42, 100)).toBe("42/100");
  });

  it("falls back to Pending without a score or max", () => {
    expect(formatDetectionScore(null, 100)).toBe("Pending");
    expect(formatDetectionScore(10, null)).toBe("Pending");
    expect(formatDetectionScore(10, 0)).toBe("Pending");
  });
});

describe("detectionPercent", () => {
  it("rounds to the nearest percent", () => {
    expect(detectionPercent(1, 3)).toBe(33);
    expect(detectionPercent(50, 200)).toBe(25);
  });

  it("returns null when data is missing", () => {
    expect(detectionPercent(undefined, 100)).toBeNull();
    expect(detectionPercent(5, 0)).toBeNull();
  });
});

describe("status labels", () => {
  it("maps evidence statuses to readable labels", () => {
    expect(formatEvidenceStatus("pending-analysis")).toBe("Pending Analysis");
    expect(formatEvidenceStatus("analysis-failed")).toBe("Analysis Failed");
    expect(formatEvidenceStatus("investigating")).toBe("Investigating");
  });

  it("maps OCR and analysis job statuses", () => {
    expect(formatOcrStatus("not-started")).toBe("Not Started");
    expect(formatOcrStatus("not-applicable")).toBe("Not Applicable");
    expect(formatAnalysisJobStatus("processing")).toBe("Processing");
  });

  it("maps evidence sources", () => {
    expect(formatEvidenceSource("manual-upload")).toBe("Manual Upload");
    expect(formatEvidenceSource("telegram")).toBe("Telegram");
  });
});

describe("formatEvidenceDateTime", () => {
  it("includes day, month, year and time for an ISO timestamp", () => {
    const result = formatEvidenceDateTime("2024-08-15T10:30:00Z");
    expect(result).toContain("2024");
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });
});
