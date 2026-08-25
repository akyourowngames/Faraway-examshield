# ExamShield Skill Registry

Discovery-only catalog. The runtime loads a skill's full `SKILL.md` only after
selecting it from this table.

| Skill | What it does | Trigger / use case |
|-------|--------------|--------------------|
| `watermark-analysis` | Summarize watermark reliability | Evidence has watermark candidate/confidence |
| `ocr-quality` | Gate OCR reliability | Evidence has OCR text/confidence |
| `text-similarity` | Non-hallucinated text/registry matching | Suspicious text vs registered papers |
| `attribution-analysis` | Consolidate signals into source attribution | Watermark/registry/text signals exist |
| `threat-assessment` | Facts-first case-level risk posture | A consolidated risk view is needed |
| `evidence-completeness` | Check evidence chain readiness | Before attribution/escalation |
| `policy-evaluator` | Deterministic policy decision | Structured signals + a policy |
| `policy-simulator` | Preview current vs proposed policy | Policy impact analysis |

Machine-readable source: [`registry.json`](registry.json).
