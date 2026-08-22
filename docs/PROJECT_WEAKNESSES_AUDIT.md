# Faraway ExamShield — Project Weaknesses & Technical Audit

> **Scope:** Full repository audit of `D:\Projects\Faraway-examshield` (cloned from
> `https://github.com/akyourowngames/Faraway-examshield.git`). Findings are grounded in actual source
> files. Where a claim is inferred rather than directly observed, it is marked **[INFERRED]**. Items that
> could not be verified are marked **[UNVERIFIED]**.
>
> **Audience:** Senior software architect, security engineer, DevOps, and technical due-diligence teams.

---

## 1. Executive Summary

### 1.1 Scorecard

| Dimension | Score (0–10) | Basis |
|-----------|--------------|-------|
| Overall project quality | **5.5** | Clean module boundaries in the backend; coherent frontend; but systemic security, authz, and ops gaps. |
| Production readiness | **3.5** | No RLS policies, unauthenticated backend API, no CI, free-tier single-process backend. |
| Security | **3.5** | Service-role-only trust, binary auth, default-open CORS. |
| Scalability | **4.0** | `http.server` single process, worker pool capped at 2, Render free plan (spins down), no caching layer. |
| Maintainability | **5.0** | Readable Python/TS, but hand-rolled HTTP routing, no migrations, no frontend tests, magic numbers. |
| Performance | **5.0** | OCR budget dominates latency; no response caching for read GETs; vector memory search has no time bound; blocking file I/O (O(n) per request); `ThreatMap` shipped in the initial dashboard bundle. Single-process Python + GIL is an infra ceiling (§5/§14). |
| Documentation | **7.0** | Strong README + `docs/DEPLOYMENT.md` + `TELEGRAM_SETUP.md`; no API/OpenAPI spec; architecture doc separate. |
| Code quality | **6.0** | Mostly consistent; notable smells (string-cast embeddings, naive redaction, duplicated config). |
| Technical debt | **6.0** | High but tractable: RLS, CI, migrations, encryption, RBAC, observability. |

### 1.2 How scores were determined

* **Security (3.0):** Hard evidence — `supabase/schema.sql` enables RLS on every table but defines **no
  policies**; the backend uses `service_role` (`store.py:1631`); `middleware.ts` protects only `/dashboard` and **not** `/api/*`;
  `EXAMSHIELD_AI_CORS_ORIGIN` previously defaulted to `*`; it is now allow-list validated (`settings.py`).
* **Scalability (4.0):** The API is `ThreadingHTTPServer` with `AnalysisWorkerPool(max_workers=2)`
  (`workers.py`), deployed on Render **free** plan (`render.yaml`), which spins down after inactivity.
* **Production readiness (3.0):** No `.github/` workflows (verified absence), no `supabase/migrations/`,
  no health-probe beyond `/health`.
* **Maintainability (5.0):** Backend is modular (`server.py`, `store.py`, `ocr.py`, `pipeline.py`,
  `tools.py`, `memory.py`, …) but uses the standard library HTTP server with manual routing; frontend has
  **no test suite** (no `web/tests`, no vitest/jest config found).
* **Performance (5.0):** Chat pays a separate planner LLM call per turn (`ToolPlanner.plan`, ~4s)
  before answering; no response caching for read GETs; vector memory search has no time bound;
  blocking file I/O (O(n) per request); `ThreatMap` is shipped in the initial dashboard bundle
  (§5/§14). Single-process Python + GIL is an infra/deployment ceiling (§5/§14).
* **Documentation (7.0):** README is thorough; deployment and Telegram docs are accurate; but no API
  contract, no ADR, no security model writeup beyond the architecture doc.

---

## 2. Critical Issues (Highest Priority)

### 2.1 No Row-Level Security policies (Critical)
* **Affected:** `supabase/schema.sql` (all tables).
* **Root cause:** RLS is enabled but no `CREATE POLICY` statements exist; the design relies entirely on
  the backend's `service_role` key.
* **Impact:** Any process holding the service-role key can read/write **all** tenants' data. Combined with
  §2.2, this is the single largest blast-radius issue.
* **Fix:** Define least-privilege RLS policies; rotate to a dedicated backend role; keep `service_role` out
  of app code paths where possible.
* **Effort:** M (1–2 days + testing).

### 2.2 Backend API has no authentication/authorization (Critical)
* **Affected:** `apps/ai-service/examshield_ai/server.py`, `render.yaml`.
* **Root cause:** Endpoints (`/evidence`, `/analysis/jobs`, `/memory/*`, `/agents/*`, `/telegram/*`,
  `/registry/match`, `/chat`, `/plan`) are reachable anonymously; protection is expected to come from the
  Vercel proxy / network isolation.
* **Impact:** If the Render URL is ever exposed (misconfig, DNS leak, link in error page), an attacker can
  read all evidence, inject Telegram events, or run OCR/AI at the operator's cost.
* **Fix:** Require a shared secret / mTLS / Vercel-only IP allow-list; or move auth into the API.
* **Effort:** M (1–3 days).

---

## 3. Architecture Weaknesses

* **Monolithic single-process backend.** `server.py` uses `http.server.ThreadingHTTPServer` — adequate
  for a demo but lacking connection pooling, graceful shutdown hooks, request size limits, and
  production-grade concurrency. There is no ASGI/WSGI server (e.g. Gunicorn/Uvicorn).
* **No clear layering contract.** Route handlers in `server.py` reach directly into `store`, `pipeline`,
  `tools`, `memory`, and `telegram`. Business logic is intermixed with HTTP concerns (e.g.
  `_run_ocr`, `_upload_evidence`). A thin "service" layer would improve testability.
* **Tight coupling to Supabase internals.** `store.py` calls the Supabase REST API directly
  (`_supabase_json`, `_supabase_bytes` with hardcoded `/rest/v1/...` paths and RPC names). Switching
  providers or even upgrading the client would require broad changes.
* **Graceful-degradation dual store is a double-edged sword.** The local-JSON fallback keeps offline dev
  working, but it diverges from the production schema and can mask data-layer bugs that only appear on
  Supabase.
* **Frontend is a pure proxy shell for most data.** `web/src/app/api/**/route.ts` handlers are near-empty
  pass-throughs to the backend (`proxyApi`). This is fine for secret isolation but means the frontend has
  almost no server-side caching, validation, or aggregation layer.
* **[INFERRED] No event bus / queue.** OCR and memory correlation are driven by in-process thread pools
  and a stale-job sweeper (`server.py:_start_stale_job_sweeper`). There is no durable queue (e.g. Redis/
  RabbitMQ/Postgres `pgmq`), so a process crash mid-job relies on `recover_interrupted_jobs` — which only
  re-queues jobs already marked `processing`.
* **Unused / stub modules shipped in the tree.** `apps/vision` (experimental YOLO) and
  `apps/broadcast-agent` (only `.env.example`) add cognitive load and confuse the deployment boundary
  (only `apps/ai-service` is built by `Dockerfile`).

---

## 4. Security Audit

| # | Issue | Severity | Files |
|---|-------|----------|-------|
| S1 | No RLS policies (service-role trust) | Critical | `schema.sql` |
| S2 | Unauthenticated backend API | Critical | `server.py`, `render.yaml` |
| S3 | Default-open CORS — now allow-list validated (was `*`) | Fixed | `settings.py`, `server.py` |
| S4 | Binary auth only — no RBAC/roles | High | `middleware.ts`, `web/src` |
| S5 | `middleware.ts` excludes `/api/*` from auth checks | Medium | `middleware.ts` matcher |
| S6 | Secrets only on Render | Medium | `render.yaml`, `store.py` |
| S7 | Naive PII redaction (`memory.redact_text`) can miss obfuscated identifiers | Medium | `memory.py` |
| S8 | No CSP/HSTS/security headers configured (`next.config.ts` empty) | Medium | `web/next.config.ts` |
| S9 | OCR.space key transmitted via HTTP header `apikey` to third party | Low/Info | `ocrspace.py` |
| S10 | Telegram webhook secret optional (`TELEGRAM_WEBHOOK_SECRET` may be empty → `validate_secret` no-ops) | Medium | `telegram.py` |
| S11 | Error messages can leak internals (e.g. `str(exc)` returned to client) | Low | `server.py` handlers |
| S12 | No audit log of who accessed/modified evidence (activity JSON is event-based, not access-based) | Medium | `store.py` |

---

## 5. Performance Analysis

* **Chat planner latency (resolved).** The audit noted each `/chat` ran `ToolPlanner.plan` (LLM call,
  ~4s) before answering. The chat path now uses a zero-LLM `classify_turn_intent` heuristic to decide
  whether to attach tool schemas, so there is no separate planning round-trip; results are memoised so
  repeated prompts (e.g. the same greeting) are not re-classified. `ToolPlanner` remains only for the
  explicit `/plan` endpoint.
* **Single-process Python + GIL.** Heavy OCR (OpenCV, Tesseract subprocess) and embeddings block the
  event loop; `AnalysisWorkerPool(max_workers=2)` caps throughput at ~2 concurrent OCR jobs.

---

## 6. Code Quality Review

* **Magic numbers / hardcoded values:** `detect_threshold=7`, severity cutoffs `25/15/7` (`detect.py`),
  `qualityScore>=25` (`ocr.py`), chat tokens `220/120`, `max_upload_bytes=12MB`, `port 8790`. Many live in
  `settings.py` (good) but severities in `detect.py` are scattered constants.
* **Long functions:** `server.py` handlers and `store.py` methods (e.g. `run_analysis_job`,
  `run_attribution_for_evidence`) are large and branch-heavy; `tools.py` `with_context`/`answer_context`
  logic is intricate.
* **Duplicated config:** NVIDIA base URL, model names, and fallback lists are repeated across `settings.py`,
  `llm.py`, `planner.py`, `render.yaml`, and README — a change in one place can silently diverge.
* **Type safety (frontend OK, backend weak):** TypeScript is strict-ish (`web/tsconfig.json`); the Python
  backend has **no type checker configured** (no `mypy`/`pyright` in `requirements.txt` or scripts).
* **Error handling inconsistency:** Some handlers return `{"error": str(exc)}` (leaking internals, S16);
  others wrap gracefully. Memory/Telegram failures are logged-and-continue, which can hide data loss.
* **Naming:** Mixed `snake_case` (Python) and `camelCase` (TS) — expected per language; however
  `api_key_encrypted` vs `apiKeyEncrypted`, and `evidenceId` vs `evidence_id` cross the boundary
  (`normalize_*` helpers exist but are applied inconsistently).
* **Comments:** Generally adequate; some are aspirational ("SOAR-grade encryption" in README) not matched
  by code.
* **Dead/placeholder code:** `apps/broadcast-agent` only has `.env.example`; `apps/vision` is unused by the
  pipeline.

---

## 7. Frontend Weaknesses

* **No form validation library.** Auth and agent forms rely on manual checks; no `zod`/`react-hook-form`/
  `yup` present in `web/package.json`.
* **No global state/query cache.** Data fetching is raw `fetch` in `agent-api.ts`/`analysis-client.ts`;
  no React Query/SWR → duplicated fetches, no dedup, no optimistic UI.
* **Accessibility (a11y):** **[INFERRED]** Heavy use of `lucide-react` icons, animation, and a black
  command-center theme suggests limited focus management / contrast checks; no a11y audit found.
* **Loading & error states:** Each `/api/*` proxy can fail (502/503); the UI surfaces are **[UNVERIFIED]**
  for consistent error boundaries — no global `error.tsx`/`loading.tsx` observed in the tree listing.
* **Responsiveness:** README claims mobile optimization, but `react-simple-maps` + `recharts` can be
  heavy on low-end devices; no performance budget set.
* **Animations:** `framer-motion` is powerful but unguarded `prefers-reduced-motion` handling was not
  observed.
* **UX:** The agent builder, registry upload, and investigation workspace are rich, but there is no
  apparent guided onboarding, empty states, or toasts system referenced in `package.json` (no `sonner`/
  `react-toastify`).
* **No i18n** for a product explicitly targeting Indian exam boards (NEET/JEE) — UI is English-only
  **[INFERRED]**.

---

## 8. Backend Weaknesses

* **HTTP server choice:** `http.server` is not built for production traffic; no keep-alive tuning, no
  request body size cap at the server level, no timeout on slow clients.
* **Validation:** Manual (`require_text`, `optional_text`, multipart parsing via `cgi.FieldStorage`
  — **deprecated in Python 3.13+**). Inconsistent field validation across endpoints.
* **Error handling:** Mix of raised exceptions and returned error dicts; no centralised error middleware.
* **Logging:** `logging.basicConfig` to stdout is fine for containers, but there is no structured logging
  (JSON), no log levels per route, no correlation IDs across OCR→memory→alert.
* **Background jobs:** `AnalysisWorkerPool` is in-process; a deploy/restart loses in-flight jobs unless
  they were marked `processing` (see §3). No retry queue with backoff beyond a single timeout.
* **Configuration:** Sensible env-driven design in `settings.py`, but `render.yaml` hardcodes many values
  that duplicate `settings.py` defaults → drift risk.
* **Dependency management:** Only OpenCV + pytest declared; everything else is stdlib. This is good for
  supply-chain surface but means future needs must be added manually; `fitz` (PyMuPDF) is now declared in
  `requirements.txt`, so PDF ingestion no longer breaks on a clean deploy.

---

## 9. Database Weaknesses

* **No RLS policies** (§2.1, §4-S1) — the most serious DB issue.
* **No foreign-key enforcement between core domain tables.** `examshield_documents` is a generic
  `(collection, document_key)` JSON bag; relationships (evidence↔report↔attribution↔alert↔memory) are
  enforced in **application code**, not the schema → referential integrity can drift.
* **JSONB overuse.** Storing structured entities as `payload jsonb` loses type safety, indexing, and
  queryability; you cannot efficiently query inside `payload` without expression indexes.
* **No transactions across collections.** Multi-document writes (evidence + activity + watermark) are
  sequential REST calls; a failure mid-way leaves partial state.
* **Vector index only `WHERE embedding IS NOT NULL`** — fine, but there is no `ivfflat` alternative and no
  tuning of `hnsw` `m`/`ef` parameters.
* **No migration system.** Single `schema.sql` applied manually; no `supabase/migrations/`, so schema
  evolution is unversioned and not reviewable in CI.
* **Backup strategy [UNVERIFIED]:** Relies on Supabase managed backups; no app-level export/restore
  documented.
* **Storage buckets** `evidence-files`, `agent-knowledge` are private but accessed via `service_role`
  only; no signed-URL short-lived access for the frontend (frontend must proxy through backend).

---

## 10. Authentication Weaknesses

* **Login/logout:** Supabase handles email/password + Google/GitHub OAuth; no custom password policy beyond
  Supabase defaults **[INFERRED]** (no MFA, no lockout, no CAPTCHA configured in repo).
* **Session lifecycle:** Cookie sessions via `@supabase/ssr`; middleware refreshes on each request. No
  explicit server-side session invalidation/listing.
* **OAuth:** Callback at `app/auth/callback/route.ts`; standard. No state/CSRF note beyond Supropy's PKCE
  (Supabase default).
* **Protected routes:** Only `/dashboard` is gated. `authRoutes` redirect logic is correct, but API routes
  are explicitly excluded from the matcher.
* **RBAC / permission model:** **Absent.** Any authenticated user reaches every dashboard and, via the
  proxy, every backend capability. No roles, no scopes, no per-agent ownership checks.
* **Session expiration:** Delegated to Supabase; no short-lived custom session for the admin/operator
  surface.
* **Token storage:** Cookies managed by Supabase SSR; acceptable, but no `SameSite`/secure overrides
  configured in app code (relies on Supabase defaults).

## 11. AI & OCR Weaknesses

### 11.1 OCR
* **Accuracy depends on print quality & language.** Tesseract `--oem 1 --psm 6,4` with `eng` only; no
  Indic-script OCR (relevant for Indian exam leaks in regional languages).
* **Quality heuristic is heuristic.** `score_ocr_quality` derives a 0–100 score from word/vowel ratios and
  penalties; it can pass noisy text or reject valid short text. `OCR_MIN_QUALITY=25` is low.
* **No deskew/denoise pre-processing** beyond downscale; skewed/photographed papers may OCR poorly.
* **Chain ordering & cost.** `ocrspace,tesseract` tries the *paid* cloud first; each OCR.space call costs
  quota. No caching of OCR results for identical images (by hash).
* **Timeout handling:** Tesseract subprocess uses `timeout=call_timeout`; a hang terminates the attempt but
  the whole 120s budget can be consumed.

### 11.2 AI
* **Planner on every turn (resolved).** The chat path no longer runs `ToolPlanner.plan` per turn; it uses
  the memoised `classify_turn_intent` classifier, so "no-tool-needed" decisions are now cached and greetings
  skip tool schemas entirely.
* **Hallucination handling:** Tool results are injected as `model_context` with instructions to not
  fabricate, but the LLM still generates free text; no verification of cited numbers against source data.
* **Fallback is model-list only.** `llm._candidate_models` iterates primary→fallbacks on *any* error, which
  can mask a bad request (e.g. 400) by retrying against a different model that also fails.
* **No token/rate budgeting per tenant** for the NVIDIA key; a single user could exhaust quota.
* **Embeddings (RAG):** `rag.py` previously cast vectors to strings, breaking search; it now stores the
  real `vector(384)` list, consistent with `memory.py` (fixed).
* **Streaming robustness:** `stream_chat` raises if all models fail; the SSE client must handle abrupt
  stream end (no final `done` event on hard error).

---

## 12. DevOps Weaknesses

* **No CI/CD.** No `.github/` workflows (verified). No lint/test/build gate on PRs. README badges imply
  GitHub Actions but none are committed.
* **Dockerfile:** Sensible (`python:3.12-slim`), but `COPY . .` copies the *entire* repo (including `node_modules`
  if present, large `apps/api/uploads`, `.git`) into the image; `.dockerignore` mitigates some but not all.
  Build context is large.
* **Health check is minimal.** `/health` returns OK even if Supabase/NVIDIA/Telegram are misconfigured; it
  reports `storage` and `ocr.runtime` but does **not** fail the check when dependencies are down.
* **Rollback:** Render supports it, but no DB migration/rollback strategy (no migrations, §9).
* **Monitoring/observability:** Stdout logs only; no metrics endpoint, no OpenTelemetry, no external APM.
  `[UNVERIFIED]` no Sentry/Datadog.
* **Secrets management:** Render env vars `sync:false` → must be set manually; high risk of drift between
  local `.env`, `render.yaml`, and `settings.py`. No secrets scanner configured.
* **Environment parity:** Local uses local-JSON fallback; prod uses Supabase. Divergent code paths (§3).

---

## 13. Dependency Audit

| Package | Concern | Note |
|---------|---------|------|
| `next@16.2.7` | Very new major; bleeding-edge | Pinned; fine but watch for breaking changes. |
| `react@19.2.4` | New; peer churn | Requires `legacy-peer-deps` (`.npmrc`). |
| `framer-motion@^12` | Heavy animation lib | Contributes to bundle; lazy-load where possible. |
| `recharts@^3` | Large charting bundle | Consider lightweight alternative or dynamic import. |
| `react-simple-maps@^3` + `@svg-maps/india` | Niche, low maintenance | Acceptable for one map; verify React 19 compat. |
| `opencv-python-headless@>=4.8.0` | Native, large wheel | Necessary for OCR preprocessing. |
| `pytest@>=8.0` | Dev only | Fine. |
| `commander`, `chalk`, `tsx` (core) | Healthy | Fine. |
| `fitz` (PyMuPDF) | Declared in `requirements.txt` (`pymupdf>=1.23.0`) | Runtime import in `rag.py`, now satisfied. |
| `ultralytics` (vision) | Experimental | Not in main pipeline; should live in a separate repo/optional extra. |
| Supabase client libs | Current | `@supabase/ssr@^0.12`, `supabase-js@^2.108` — current. |
| `eslint@^9` + `eslint-config-next` | Current flat config | Good. |

**Unused/duplicate functionality:** `apps/vision` duplicates object-detection intent that OCR+registry
already partially cover; `apps/broadcast-agent` is an empty stub. Both add maintenance surface without
shipping value.

---

## 14. Scalability Risks

| Scale | Database | API | OCR/AI | Storage | Verdict |
|-------|----------|-----|--------|---------|---------|
| ~100 users | Fine (single Postgres) | Fine (thread pool 2 OK) | OK | OK | Works |
| ~1,000 | pgvector scans grow; no caching | Single process bottleneck; Render free spins down | OCR queue saturates at 2 concurrent | OK | Needs caching + worker autoscaling |
| ~10,000 | JSONB bag + vector scans degrade; no sharding | One container = hard ceiling | NVIDIA/OCR.space quota/cost blows up | Storage egress grows | Requires queue, multiple workers, read replicas |
| ~100,000 | Schema must move off JSONB bag to relational + proper indexing; RLS required | Needs load balancer + horizontal API | Needs GPU/batch OCR, cost controls | Needs CDN + lifecycle policies | Major re-architecture |

* **Database:** generic `examshield_documents` JSON bag and absence of RLS/caching are the top scaling
  blockers.
* **API:** `ThreadingHTTPServer` + `max_workers=2` + free-tier spin-down is the hard ceiling.
* **OCR/AI:** Per-request paid external calls with no budget/queue → cost and latency explode.
* **Caching:** None at any layer; every read hits Supabase.
* **Infra:** No autoscaling, no CDN, no message broker.

---

## 15. Maintainability Issues

* ~~**No frontend tests** — zero coverage for React components/route handlers (no test runner configured in
  `web/package.json`).~~ **RESOLVED** — Vitest suite configured (`web/vitest.config.ts` + `web/tests/setup.ts`)
  with login-page render and evidence-format util tests (`npm test`); wired into the `quality-gate` GitHub
  Actions workflow.
* **Backend tests exist** (`apps/ai-service/tests/`: `test_analysis_flow`, `test_ocr`, `test_ocrspace`,
  `test_store_snapshot`, `test_telegram_pipeline`, `test_workers`, `conftest`) — good, but they are
  integration-style and depend on local filesystem/network; ~~**[UNVERIFIED]** whether they run in CI (no CI)~~
  now **verified in CI** — the `quality-gate` workflow runs ruff + pytest on every PR and push to `main`.
* **No type checking in Python** (no `mypy`/`pyright`) despite heavy use of `JsonObject` dicts.
* **Duplicated model/fallback config** across `settings.py`, `render.yaml`, `llm.py`, `planner.py`.
* **Large modules:** `server.py` (~1440 lines), `store.py` (~1900 lines), `tools.py`, `memory.py` — each is
  a "god module" with many responsibilities.
* **Magic numbers** scattered (§6).
* **Documentation gaps:** No API reference, no ADR, no threat model, no runbook for incident response.

---

## 16. Missing Features

* **Audit logging** of access/modifications (activity feed is event-based, not access-based — §4-S17).
* **Monitoring & metrics** (Prometheus/OTel), dashboards, alerting on backend health.
* **RBAC / multi-tenant scoping** (§10).
* **Search & pagination** for evidence/alerts/registry (lists return full collections).
* **Retry/DLQ** for failed OCR/AI jobs.
* **Admin tooling** (user management, key rotation, agent moderation).
* **Feature flags** for gradual rollout.
* **Backup/restore runbook** and DB migration tooling (§9).
* **i18n** for regional-language support (§7).
* **Cost guardrails** (per-tenant AI/OCR quotas).
* **Webhook signature verification UI/health** for Telegram.
* **Structured error pages / global error boundaries** in the frontend.

---

## 17. Technical Debt

| Debt | Why it exists | Impact | Priority | Resolution |
|------|--------------|--------|----------|------------|
| No RLS policies | Designed for service-role-only | Huge blast radius | P0 | Add policies + dedicated role |
| Unauthenticated API | Assumed network trust | Data exposure | P0 | Add auth/gateway |
<<<<<<< HEAD
| No CI | Time/scope | Regressions ship | P1 | GitHub Actions lint/test/build |
=======
| String embeddings in RAG | Quick prototype | Broken RAG | P1 | Store real vector |
| No CI | Time/scope | Regressions ship | P1 | ~~GitHub Actions lint/test/build~~ **DONE** — `.github/workflows/quality-gate.yml` (ruff + pytest + web typecheck/test/build) |
>>>>>>> origin/main
| No migrations | Manual schema.sql | Unversioned schema | P1 | supabase/migrations |
| No frontend tests | Time/scope | UI regressions | P2 | ~~Vitest + component tests~~ **DONE** — Vitest suite in `web/`, run in the quality gate |
| JSONB document bag | Rapid prototyping | Weak integrity/query | P2 | Relational tables |
| Duplicate config | Convenience | Drift | P2 | Single source of truth |
| Stub modules in tree | Experimentation | Confusion | P3 | Move to separate repos/optional |
| No caching layer | Simplicity | Latency/cost | P2 | Redis/edge cache |
| Deprecated `cgi.FieldStorage` | Stdlib only | Py3.13 break | P2 | `python-multipart` |

---

## 18. Risk Matrix

| Issue | Severity | Impact | Likelihood | Priority | Suggested Fix |
|-------|----------|--------|-----------|----------|---------------|
| No RLS policies | Critical | Data-wide exposure | Medium | P0 | Define least-privilege RLS |
| Unauthenticated API | Critical | Full data/abuse | Medium | P0 | API auth / gateway |
| No CI | High | Regressions | High | P1 | GitHub Actions |
| No RBAC | High | Unauthorized access | Medium | P1 | Roles/scopes |
| Binary auth only | Medium | Privilege issues | Medium | P2 | RBAC |
| Naive redaction | Medium | PII leak | Medium | P2 | Stronger redaction |
| No security headers | Medium | Browser attacks | Low | P2 | CSP/HSTS |
| JSONB bag schema | Medium | Weak integrity | Medium | P2 | Relational model |
| No caching | Medium | Latency/cost | High | P2 | Cache layer |
| Single-process API | Medium | Throughput ceiling | Medium | P2 | ASGI + workers |
| Stub/experimental modules | Low | Confusion | Low | P3 | Remove/isolate |

---

## 19. Roadmap

### Immediate (Critical — weeks 0–2)
* Add RLS policies + dedicated backend DB role (P0).
* Authenticate the backend API (shared secret / Vercel-only network / mTLS) (P0).

### Short-term (1–2 months)
* Stand up CI (lint + backend pytest + frontend tests + `next build`).
* Migrate schema to versioned `supabase/migrations/`.
* Add RBAC + per-agent ownership; protect `/api/*` in middleware.
* Add security headers (CSP/HSTS) and global error/loading boundaries.

### Medium-term (2–4 months)
* Replace stdlib HTTP server with ASGI (FastAPI/Uvicorn) + horizontal workers; add a durable queue
  (Postgres `pgmq`/Redis).
* Introduce caching (Redis/edge) for lists and embeddings lookups.
* Move domain entities out of the JSONB bag into typed relational tables with FKs.
* Add observability (OTel metrics, structured logs, health that fails on dep outage).
* Regional-language OCR + i18n.

### Long-term (4–12 months)
* Multi-tenant architecture with sharding/read replicas.
* Cost governance, SLA, audit/compliance (SOC2-style controls).
* GPU/batch OCR path; model routing with budgets and eval harness.
* Remove or productize `apps/vision` and `apps/broadcast-agent`.

---

## 20. Overall Verdict

### 20.1 Biggest strengths
* Clear, modular backend design with well-separated concerns (OCR, pipeline, tools, memory, RAG, Telegram).
* Strong product vision and a working end-to-end flow (upload → OCR → watermark → attribution → alert →
  memory correlation).
* Mature deployment docs and a sensible secret boundary (secrets on Render only).
* Backend test suite exists for core flows.
* Modern, attractive frontend using current Next.js 16 / React 19.

### 20.2 Biggest weaknesses
* **Security model is demo-grade:** no RLS, unauthenticated API, binary auth.
* **No CI, no migrations, no caching, no observability.**
* **Scalability ceiling** from single-process Python + free tier + JSONB bag.
* **Functional defect** (now resolved) in agent RAG embeddings — vectors are stored as real `vector(384)`
  values rather than strings; a missing runtime dependency (`fitz`) is also declared in `requirements.txt`.
* **Maintainability debt:** god modules, duplicate config, no frontend tests, deprecated stdlib usage.

### 20.3 Production readiness
**Not production-ready as-is (readiness 3/10).** Suitable for a pilot/demo with trusted operators on a
private network, but it must clear the P0 security items before any real deployment.

### 20.4 Suitability

| Use case | Suitable? | Justification |
|----------|-----------|--------------|
| Hackathon | ✅ Yes | Fast to demo, impressive flow. |
| MVP / startup launch (trusted users) | ⚠️ Conditional | Viable behind auth gateway + fixed P0 items. |
| Small production (≤1k users, internal) | ⚠️ Conditional | Needs RLS, auth, rate limits, caching. |
| Enterprise deployment | ❌ No | Requires RBAC, multi-tenancy, compliance, scale re-arch. |

### 20.5 Recommended next steps
1. Close all **P0** security items (RLS, API auth) before any external exposure.
2. Add **CI** + **migrations** to stop regressions and unversioned schema.
3. ~~Fix the **RAG embedding** defect and **`fitz`** dependency~~ — both resolved (real `vector(384)` storage; `pymupdf` declared).
4. Introduce a **caching + queue** layer to raise the scalability ceiling.
5. Plan a phased move from the JSONB document bag to a relational schema with foreign keys.

---

*End of audit. Findings are evidence-based against the cloned repository; items marked **[INFERRED]** or
**[UNVERIFIED]** indicate where direct source confirmation was not available in this review pass.*
