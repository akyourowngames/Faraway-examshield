# EXAMSHIELD (Faraway)

AI-powered examination-security platform: detect leaked question papers, trace them
back to their source through forensic watermarks, and alert investigators in
real time.

[![quality-gate](https://github.com/akyourowngames/Faraway-examshield/actions/workflows/quality-gate.yml/badge.svg?branch=main)](https://github.com/akyourowngames/Faraway-examshield/actions/workflows/quality-gate.yml)
![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)

---

## What it does

1. **Ingest** leaked-paper evidence from dashboard uploads or Telegram messages
   (text, screenshots, photos).
2. **Analyze** each item: OCR (OCR.space + Tesseract), leak-keyword detection,
   watermark extraction, and matching against the question-paper registry.
3. **Attribute** the leak to a paper / center / print batch and generate a
   forensic report.
4. **Alert** investigators via Telegram and the dashboard, and remember
   correlated signals in unified threat memory for future cases.
5. **Assist** with an LLM chat assistant that can query live evidence data
   through schema-driven tools.

## Architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│  web/  (Next.js 16, Vercel) │  HTTP  │ apps/ai-service (Python, Render) │
│                             ├───────▶│                                  │
│  • Auth (Supabase JWT +     │        │  • Evidence API + local store    │
│    OAuth, middleware guard) │        │  • OCR pipeline (async workers)  │
│  • Dashboard: evidence,     │        │  • Leak detection + attribution  │
│    threat map, lifecycle    │        │  • AI chat (SSE) + tools + RAG   │
│  • Proxies /api/* to the    │        │  • Telegram webhook + pollers    │
│    backend                  │        │  • Reports, agents, memory       │
└──────────────┬──────────────┘        └──────────┬───────────┬───────────┘
               │                                  │           │
               ▼                                  ▼           ▼
      ┌─────────────────┐              ┌──────────────┐  ┌──────────┐
      │ Supabase        │              │ Tesseract +  │  │ LLM      │
      • Auth/Postgres/   │              │ OCR.space    │  │ Kilo GW  │
      • Storage/pgvector │              └──────────────┘  └──────────┘
      └─────────────────┘
```

### Repository layout

| Path | Purpose |
|------|---------|
| `web/` | Next.js 16 frontend — auth, dashboard, AI chat UI, agent studio |
| `apps/ai-service/` | Python 3.12 service: REST API, OCR pipeline, detection, chat, agents, Telegram |
| `apps/core/` | TypeScript question-paper registry + CLI (chain-of-custody records) |
| `apps/api/` | Local JSON fallback store used when Supabase is not configured |
| `supabase/` | `schema.sql` (tables/indexes) and Edge Functions |
| `docs/` | Deployment guide, tech-stack deep dive, strengths/weaknesses audits, roadmap |
| `Dockerfile` / `render.yaml` | Backend container + Render blueprint |
| `vercel.json` | Frontend deployment config |

### Key flows

- **Upload → alert**: upload → queued analysis job (`AnalysisWorkerPool`) → OCR →
  `scan_text()` leak scoring → registry match → forensic report → Telegram/dashboard alert.
- **Chat**: intent classified locally (zero LLM cost) → tool schemas attached only for
  live-data requests → model streams an answer grounded in real tool results →
  hallucination check flags claims unsupported by that data.
- **Guardrails**: per-request/per-session token budgets (`examshield_ai/budget.py`),
  transient-error retry/backoff on every LLM call, bounded OCR worker pool.

## Setup

Prerequisites: **Node.js ≥ 20**, **Python ≥ 3.12**, a **Supabase project**
(optional — the stack runs offline against local JSON without one).

### Frontend (`web/`)

```bash
cd web
npm install --legacy-peer-deps

cat > .env.local << EOF
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
EXAMSHIELD_API_URL=http://localhost:8790
# EXAMSHIELD_BACKEND_API_KEY=...   # must match backend EXAMSHIELD_API_AUTH_SECRET
EOF

npm run dev          # http://localhost:3000
```

### Backend (`apps/ai-service/`)

```bash
cd apps/ai-service
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
export KILO_API_KEY=your-kilo-gateway-key
export EXAMSHIELD_AI_CORS_ORIGIN=http://localhost:3000

python run.py        # serves http://0.0.0.0:8790 (health at /health)
```

Without Supabase/KILO variables the service still boots: evidence goes to the
local JSON store and chat answers degrade to a visible local fallback.

### Docker

```bash
docker build -t examshield-api .
docker run -p 8790:8790 --env-file apps/ai-service/.env examshield-api
```

## Environment variables

### Frontend (Vercel / `web/.env.local`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | Public anon key |
| `EXAMSHIELD_API_URL` | no | Backend base URL for `/api` proxying (defaults to same-origin) |
| `EXAMSHIELD_API_TIMEOUT_MS` / `EXAMSHIELD_API_RETRIES` | no | Proxy timeout/retry tuning |

### Backend (Render / `apps/ai-service/.env`)

Core:

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_URL` | prod* | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | prod* | Service-role key |
| `KILO_API_KEY` | no* | LLM gateway key (chat/planner disabled without it) |
| `EXAMSHIELD_AI_CORS_ORIGIN` | yes | Allowed browser origin |
| `EXAMSHIELD_PUBLIC_URL` | no | Public backend URL (Telegram webhooks) |
| `PORT` | no | Listen port (default `8790`) |

LLM & guardrails:

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXAMSHIELD_AI_MODEL` | `tencent/hy3:free` | Chat model |
| `EXAMSHIELD_AI_FALLBACK_MODELS` | comma list | Fallback chain |
| `EXAMSHIELD_AI_PLANNER_MODEL` | `tencent/hy3:free` | Tool-planning model |
| `EXAMSHIELD_AI_LLM_RETRY_ATTEMPTS` | `2` | Retries per transient LLM failure |
| `EXAMSHIELD_AI_LLM_RETRY_BACKOFF_SECONDS` | `0.5` | Base exponential backoff |
| `EXAMSHIELD_AI_BUDGET_PER_REQUEST_TOKENS` | `4000` | Per-request token ceiling |
| `EXAMSHIELD_AI_BUDGET_PER_SESSION_TOKENS` | `50000` | Per-session token ceiling |
| `EXAMSHIELD_AI_CHAT_MAX_TOKENS` | `350` | Max completion tokens |

OCR & workers:

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXAMSHIELD_OCR_CHAIN` | `ocrspace,tesseract` | Engine order |
| `OCR_SPACE_API_KEY` | — | Enables OCR.space |
| `EXAMSHIELD_OCR_MODE` | `sequential` | `sequential` \| `parallel` PSM sweep |
| `EXAMSHIELD_OCR_WORKERS` | `2` | Analysis worker-pool size |
| `EXAMSHIELD_OCR_TOTAL_BUDGET_SECONDS` | `120` | Whole-analysis deadline |

Telegram:

| Variable | Required | Purpose |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | no | Global EXAMSHIELD bot |
| `TELEGRAM_WEBHOOK_SECRET` | no | Webhook auth |
| `TELEGRAM_CHAT_ID` / `TELEGRAM_ADMIN_CHAT_ID` | no | Alert destinations |

\* Required for production (Supabased-backed) deployments; omit them for the
offline/local fallback mode. The operational list lives in [`render.yaml`](render.yaml).

## Run commands

```bash
# Backend
cd apps/ai-service
python run.py                 # serve API + SSE chat + Telegram pollers
ruff check .                  # lint
pytest tests -q               # tests

# Frontend
cd web
npm run dev                   # dev server
npm run build                 # production build
npm test                      # Vitest suite
npx tsc --noEmit              # typecheck
```

CI (`.github/workflows/quality-gate.yml`) gates every push/PR to `main` with:
ruff + pytest (backend job) and typecheck + Vitest + build (frontend job).
Direct pushes to `main` are discouraged — open a PR instead.

## API surface (backend)

| Area | Endpoint |
|------|----------|
| Health/config | `GET /health`, `GET /` |
| Evidence | `POST /evidence/upload`, `GET /evidence/list`, `GET /evidence/{id}` |
| Chat | `POST /chat` (SSE stream) |
| Tools/planner | `POST /plan`, `GET /tools` |
| Agents | `POST /agents/{id}/test`, knowledge CRUD, deploy/status |
| Reports | `POST /reports/generate` |
| Telegram | `POST /telegram/webhook`, `GET /telegram/events` |

## Documentation

- [Deployment walkthrough](docs/DEPLOYMENT.md)
- [Tech stack & architecture](docs/TECH_STACK_ARCHITECTURE.md)
- [Strengths audit](docs/PROJECT_STRENGTHS.md) · [Weaknesses audit](docs/PROJECT_WEAKNESSES_AUDIT.md)
- [Learning roadmap](docs/LEARNING_ROADMAP.md)

## Contributing

1. Branch from `main` (one branch per PR); never push directly to `main`.
2. Keep CI green — ruff, pytest, typecheck, Vitest, and build must pass.
3. Open a PR with a short description of what changed and why.

## License

EXAMSHIELD — proprietary software. Copyright © 2026 Faraway Technologies.
All rights reserved.
