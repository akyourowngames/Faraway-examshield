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
| Production readiness | **3.5** | Unauthenticated backend API and free-tier single-process backend remain (CI now gated, §12). |
| Security | **3.5** | `service_role` still used for system paths, binary auth, default-open CORS. |
| Scalability | **4.0** | `http.server` single process, worker pool capped at 2, Render free plan (spins down), no caching layer. |
| Maintainability | **5.0** | Readable Python/TS, but hand-rolled HTTP routing, magic numbers. (A Vitest frontend suite now exists, §15/§17.) |
| Performance | **5.0** | OCR budget dominates latency; no response caching for read GETs; vector memory search has no time bound; blocking file I/O (O(n) per request); `ThreatMap` shipped in the initial dashboard bundle. OCR worker pool is now bounded + load-shedding (§5); single-process Python + GIL remains an infra ceiling (§14). |
| Documentation | **7.0** | Strong README + `docs/DEPLOYMENT.md` + `TELEGRAM_SETUP.md`; no API/OpenAPI spec; architecture doc separate. |
| Code quality | **6.0** | Mostly consistent; notable smells (string-cast embeddings, naive redaction, duplicated config). |
| Technical debt | **6.0** | High but tractable: encryption, RBAC, observability. |

### 1.2 How scores were determined

* **Security (3.0):** Hard evidence — the backend uses `service_role` for system paths;
  `middleware.ts` protects only `/dashboard` and **not** `/api/*`; `EXAMSHIELD_AI_CORS_ORIGIN` previously
  defaulted to `*`; it is now allow-list validated (`settings.py`).
* **Scalability (4.0):** The API is `ThreadingHTTPServer` with `AnalysisWorkerPool(max_workers=2)`
  (`workers.py`), deployed on Render **free** plan (`render.yaml`), which spins down after inactivity.
* **Production readiness (3.0):** CI now present (`.github/workflows/ci.yml`, §12); still no
  health-probe beyond `/health`.
* **Maintainability (5.0):** Backend is modular (`server.py`, `store.py`, `ocr.py`, `pipeline.py`,
  `tools.py`, `memory.py`, …) but uses the standard library HTTP server with manual routing; frontend now
  has a Vitest suite (component tests for `login` + pure formatting/util tests, run in CI via
  `npm run test`).
* **Performance (5.0):** Chat pays a separate planner LLM call per turn (`ToolPlanner.plan`, ~4s)
  before answering; no response caching for read GETs; vector memory search has no time bound;
  blocking file I/O (O(n) per request); `ThreatMap` is shipped in the initial dashboard bundle
  (§5/§14). OCR worker pool is now bounded + load-shedding (§5); single-process Python + GIL remains an
  infra/deployment ceiling (§14).
* **Documentation (7.0):** README is thorough; deployment and Telegram docs are accurate; but no API
  contract, no ADR, no security model writeup beyond the architecture doc.

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
* **Dead/placeholder modules — ✅ Resolved (§6.6):** `apps/vision` and `apps/broadcast-agent` were removed
  from the tree; only `apps/ai-service` is built by `Dockerfile`.

---

## 4. Security Audit

| # | Issue | Severity | Files |
|---|-------|----------|-------|
| S3 | Default-open CORS — now allow-list validated (was `*`) | Fixed | `settings.py`, `server.py` |
| S4 | Binary auth only — no RBAC/roles | High | `middleware.ts`, `web/src` |
| S5 | `middleware.ts` excludes `/api/*` from auth checks | Medium | `middleware.ts` matcher |
| S6 | Secrets only on Render | Medium | `render.yaml`, `store.py` |
| S7 | Naive PII redaction (`memory.redact_text`) can miss obfuscated identifiers | Medium | `memory.py` |
| S8 | No CSP/HSTS/security headers configured (`next.config.ts` empty) | Medium | `web/next.config.ts` |
| S9 | OCR.space key transmitted via HTTP header `apikey` to third party | Low/Info | `ocrspace.py` |
| S10 | Telegram webhook secret optional (`TELEGRAM_WEBHOOK_SECRET` may be empty → `validate_secret` no-ops) | Medium | `telegram.py` |
| S11 | Error messages could leak internals (`str(exc)` to client) — ✅ Resolved (§6.3): handlers now return fixed, client-safe messages via `_error_payload` | Low | `server.py` |
| S12 | No audit log of who accessed/modified evidence (activity JSON is event-based, not access-based) | Medium | `store.py` |

---

## 7. Frontend Weaknesses

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

---

## 12. DevOps Weaknesses

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
* **CI is now present (✅ Resolved):** `.github/workflows/ci.yml` runs on push to `main` and on PRs. It gates the
  backend (`apps/ai-service`: `ruff check`, `mypy examshield_ai`, `pytest`) and the frontend (`web`: `npm run lint`,
  `npm run build`) with placeholder `NEXT_PUBLIC_*` Supabase values so the build prerenders. `concurrency` cancels
  superseded runs. Remaining gaps from this section (Dockerfile context, health-check depth, no migrations/observability,
  secrets drift) are still open.

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
| `ultralytics` (vision) | Experimental | ✅ Resolved (§6.6): `apps/vision` deleted, so no longer a dependency. |
| Supabase client libs | Current | `@supabase/ssr@^0.12`, `supabase-js@^2.108` — current. |
| `eslint@^9` + `eslint-config-next` | Current flat config | Good. |

**Unused/duplicate functionality — ✅ Resolved (§6.6):** `apps/vision` and `apps/broadcast-agent` were
removed from the tree; no duplicate object-detection intent remains in the pipeline.

---

## 14. Scalability Risks

| Scale | Database | API | OCR/AI | Storage | Verdict |
|-------|----------|-----|--------|---------|---------|
| ~100 users | Fine (single Postgres) | Fine (thread pool 2 OK) | OK | OK | Works |
| ~1,000 | pgvector scans grow; no caching | Single process bottleneck; Render free spins down | OCR queue saturates at 2 concurrent | OK | Needs caching + worker autoscaling |
| ~10,000 | JSONB bag + vector scans degrade; no sharding | One container = hard ceiling | NVIDIA/OCR.space quota/cost blows up | Storage egress grows | Requires queue, multiple workers, read replicas |
| ~100,000 | Schema must move off JSONB bag to relational + proper indexing | Needs load balancer + horizontal API | Needs GPU/batch OCR, cost controls | Needs CDN + lifecycle policies | Major re-architecture |

* **Database:** generic `examshield_documents` JSON bag and absence of caching are the top scaling
  blockers.
* **API:** `ThreadingHTTPServer` + `max_workers=2` + free-tier spin-down is the hard ceiling.
* **OCR/AI:** Per-request paid external calls with no budget/queue → cost and latency explode.
* **Caching:** None at any layer; every read hits Supabase.
* **Infra:** No autoscaling, no CDN, no message broker.

---

## 15. Maintainability Issues

* **Backend tests exist** (`apps/ai-service/tests/`: `test_analysis_flow`, `test_ocr`, `test_ocrspace`,
  `test_store_snapshot`, `test_telegram_pipeline`, `test_workers`, `conftest`) — good, but they are
  integration-style and depend on local filesystem/network; they now run in CI (`.github/workflows/ci.yml`, §12).
* **No type checking in Python — ✅ Resolved (§6.2):** `mypy` is configured (`pyproject.toml`
  `[tool.mypy]`), enforced in CI (`.github/workflows/ci.yml`), and the backend type-checks clean; new
  code is fully annotated.
* **Duplicated model/fallback config — ✅ Resolved (§6.1):** defaults centralized in `settings.py`
  (`DEFAULT_MODEL`/`DEFAULT_BASE_URL`/`DEFAULT_FALLBACK_MODELS`); `render.yaml` is drift-guarded by
  `tests/test_config_consistency.py`.
* **Large modules:** `server.py` (~1440 lines), `store.py` (~1900 lines), `tools.py`, `memory.py` — each is
  a "god module" with many responsibilities.
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
| JSONB document bag | Rapid prototyping | Weak integrity/query | P2 | Relational tables |
| Duplicate config | Convenience | Drift | P2 | Single source of truth |
| Stub modules in tree | Experimentation | Confusion | P3 | Move to separate repos/optional |
| No caching layer | Simplicity | Latency/cost | P2 | Redis/edge cache |
| Deprecated `cgi.FieldStorage` | Stdlib only | Py3.13 break | P2 | `python-multipart` |

---

## 18. Risk Matrix

| Issue | Severity | Impact | Likelihood | Priority | Suggested Fix |
|-------|----------|--------|-----------|----------|---------------|
| No CI | High | Regressions | High | P1 | GitHub Actions — ✅ Resolved: `.github/workflows/ci.yml` gates backend (ruff/mypy/pytest) and frontend (lint/build) on push + PR (§12). |
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
* Authenticate the backend API (shared secret / Vercel-only network / mTLS) (P0).

### Short-term (1–2 months)
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
* ✅ Resolved (§6.6): `apps/vision` and `apps/broadcast-agent` removed from the tree.

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
* **Security model is demo-grade:** unauthenticated API and binary auth remain.
* **No migrations, no caching, no observability.** (CI is now present — §12/§18.)
* **Scalability ceiling** from single-process Python + free tier + JSONB bag.
* **Functional defect** in agent RAG embeddings — vectors are stored as real `vector(384)`
  values rather than strings; a missing runtime dependency (`fitz`) is also declared in `requirements.txt`.
* **Maintainability debt:** god modules, duplicate config, deprecated stdlib usage. (Frontend now has a Vitest suite, §15.)

### 20.3 Production readiness
**Not production-ready as-is (readiness 3/10).** Suitable for a pilot/demo with trusted operators on a
private network, but it must clear the P0 security items before any real deployment.

### 20.4 Suitability

| Use case | Suitable? | Justification |
|----------|-----------|--------------|
| Hackathon | ✅ Yes | Fast to demo, impressive flow. |
| MVP / startup launch (trusted users) | ⚠️ Conditional | Viable behind auth gateway + fixed P0 items. |
| Small production (≤1k users, internal) | ⚠️ Conditional | Still needs auth, rate limits, caching. |
| Enterprise deployment | ❌ No | Requires RBAC, multi-tenancy, compliance, scale re-arch. |

### 20.5 Recommended next steps
1. Close all **P0** security items — API auth still outstanding — before any external exposure.
2. Add **migrations** to stop unversioned schema evolution. (**CI** is now present — §12/§18.)
3. Introduce a **caching + queue** layer to raise the scalability ceiling.
4. Plan a phased move from the JSONB document bag to a relational schema with foreign keys.

---

*End of audit. Findings are evidence-based against the cloned repository; items marked **[INFERRED]** or
**[UNVERIFIED]** indicate where direct source confirmation was not available in this review pass.*
