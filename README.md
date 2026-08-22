<div align="center">
  <br/>
  <pre>
███████╗██╗  ██╗ █████╗ ███╗   ███╗███████╗██╗  ██╗██╗███████╗██╗     ██████╗
██╔════╝╚██╗██╔╝██╔══██╗████╗ ████║██╔════╝██║  ██║██║██╔════╝██║     ██╔══██╗
█████╗   ╚███╔╝ ███████║██╔████╔██║███████╗███████║██║█████╗  ██║     ██║  ██║
██╔══╝   ██╔██╗ ██╔══██║██║╚██╔╝██║╚════██║██╔══██║██║██╔══╝  ██║     ██║  ██║
███████╗██╔╝ ██╗██║  ██║██║ ╚═╝ ██║███████║██║  ██║██║███████╗███████╗██████╔╝
╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝
  </pre>
  <h3>🔐 AI-Powered Paper Leak Prevention & Forensic Watermark Tracing</h3>
  <p><i>Enterprise-grade examination security — zero-trust architecture, real-time threat intelligence</i></p>
  <br/>

  [![Live Demo](https://img.shields.io/badge/LIVE_DEMO-🔗_faraway--examshield.vercel.app-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://faraway-examshield.vercel.app)
  [![Next.js](https://img.shields.io/badge/Next.js_16-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
  [![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.io)
  [![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
  [![Tailwind](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
  [![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
  [![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
  [![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://vercel.com)
  [![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://render.com)

  <br/>

  [![Build Status](https://img.shields.io/github/actions/workflow/status/risuhfoundry/Faraway-examshield/ci.yml?branch=main&style=flat-square&label=BUILD&color=22c55e)](https://github.com/risuhfoundry/Faraway-examshield/actions)
  [![Last Commit](https://img.shields.io/github/last-commit/risuhfoundry/Faraway-examshield?style=flat-square&label=LAST_UPDATED&color=6366f1)](https://github.com/risuhfoundry/Faraway-examshield/commits)
  [![License](https://img.shields.io/badge/LICENSE-PROPRIETARY-ef4444?style=flat-square)]()
  [![PRs](https://img.shields.io/badge/PRs-WELCOME-22c55e?style=flat-square)]()

  <br/>
</div>

---

- **Evidence pipeline** — upload → OCR (Tesseract + OCR.space) → watermark extraction → paper attribution → forensic report → alerts.
- **Question Paper Registry** (`apps/core`) — chain-of-custody records (watermark, paper, exam, center, print batch, risk, status) used to match leaked papers to their source.
- **Community Agents** — per-agent system prompts, knowledge, and RAG (Supabase pgvector with a local fallback); agents reply with citations and can run as their own Telegram bots.
- **Unified threat memory** — privacy-first, cross-case correlation of leaked-paper signals (Supabase pgvector, local JSON fallback).
- **AI assistant** — streaming chat (Kilo Gateway by default; OpenAI / Anthropic / Grok / Groq / OpenCode Zen supported) with schema-driven tool routing.
- **Forensic reports** — generate Markdown evidence reports and dashboard summaries, optionally delivered to a Telegram chat (`POST /reports/generate`).
- **Multi-channel ingestion** — dashboard uploads, a Telegram webhook, and Telegram events feed the same pipeline.
- **Security** — Supabase JWT auth (email/password, Google & GitHub OAuth), Next.js middleware route protection for the dashboard, and a configurable CORS origin (`EXAMSHIELD_AI_CORS_ORIGIN`).

## 🎯 Mission Critical

> **Prevent academic integrity violations at scale** — detect paper leaks in real-time, trace watermark sources across the forensic chain, and alert authorities before compromised exams reach students.

EXAMSHIELD is a **zero-trust, end-to-end secure examination platform** combining:

- 🧠 **AI-Powered Forensics** — automatic OCR, watermark extraction, attribution matching
- 🔍 **Real-time Threat Intelligence** — multi-channel monitoring (Telegram, manual uploads)
- 🛡️ **Enterprise Security** — SOAR-grade encryption, session management, RBAC
- 📱 **Omnichannel Experience** — fully responsive desktop & mobile dashboard

---

## 🏗️ Architecture

```
examshield/
├── web/                 # Next.js 16 frontend (Vercel)
├── apps/
│   ├── ai-service/      # Unified Python API: OCR, analysis, AI chat, agents, Telegram
│   ├── core/            # TypeScript Paper Registry (chain of custody) + CLI
│   ├── api/             # Local JSON fallback store (offline mode without Supabase)
│   ├── broadcast-agent/ # Broadcast agent service
│   └── vision/          # Vision service
├── supabase/
│   ├── schema.sql       # Tables, indexes, and policies
│   └── functions/       # Edge Functions (e.g. the text-embedding endpoint)
├── docs/                # Deployment, tech-stack, roadmap, audits
├── Dockerfile           # Python 3.12 + Tesseract
├── render.yaml          # Render backend service
└── vercel.json          # Vercel frontend config
```

### 🔄 Data Flow

```
                  ┌──────────┐     ┌─────────────┐     ┌──────────┐
                  │  USER    │────▶│  NEXT.JS    │────▶│ SUPABASE │
                  │  ACTION  │     │  MIDDLEWARE  │     │   AUTH   │
                  └──────────┘     └──────┬──────┘     └────┬─────┘
                                          │                  │
                                          ▼                  ▼
                                   ┌────────────┐    ┌────────────┐
                                   │  DASHBOARD  │    │ PostgreSQL │
                                   │  PAGES      │    │  Database  │
                                   └──────┬──────┘    └────┬──────┘
                                          │                  │
                                          ▼                  ▼
                                   ┌────────────┐    ┌────────────┐
                                   │  BACKEND   │    │   EVIDENCE │
                                   │  API/PY    │    │   STORAGE  │
                                   └────────────┘    └────────────┘
```

---

## ⚡ Core Features

### 🔐 Authentication & Security
<table>
<tr>
<td width="50%">
<h4>🔑 Multi-Provider Auth</h4>
<ul>
<li>✅ Email/Password with confirmation</li>
<li>✅ Google OAuth (enterprise SSO)</li>
<li>✅ GitHub OAuth (developer access)</li>
<li>✅ JWT sessions via Supabase</li>
<li>✅ Cookie-based middleware protection</li>
</ul>
</td>
<td width="50%">
<h4>🛡️ Route Protection</h4>
<ul>
<li>✅ Auto-redirect unauthenticated → /login</li>
<li>✅ Auto-redirect authenticated → /dashboard</li>
<li>✅ Session refresh in middleware</li>
<li>✅ Secure cookie management</li>
<li>✅ Auth state listener</li>
</ul>
</td>
</tr>
</table>

### 🖥️ Dashboard Experience
<table>
<tr>
<td width="50%">

| Feature | Status |
|---------|--------|
| Command Center | ✅ Live |
| Real-time Threat Map | ✅ Active |
| Evidence Center | ✅ Active |
| AI Chat Interface | ✅ Live |
| Investigation Tools | ✅ Ready |
| Alert Center | ✅ Active |

</td>
<td width="50%">

| Feature | Status |
|---------|--------|
| Exam Lifecycle | ✅ Active |
| Settings & Profile | ✅ Active |
| Mobile Hamburger Nav | ✅ Optimized |
| Upload FAB (Mobile) | ✅ Optimized |
| Touch-Friendly UI | ✅ Implemented |
| System Reset | ✅ Active |

</td>
</tr>
</table>

### 📱 Mobile-First Experience
```
┌─────────────────────────────────────┐
│  ☰ EXAMSHIELD          🔄 🔒       │
├─────────────────────────────────────┤
│                                     │
│   ╔═══════════════════════════════╗ │
│   ║     COMMAND CENTER           ║ │
│   ║   142 Active   3 Critical    ║ │
│   ╚═══════════════════════════════╝ │
│                                     │
│   ┌────┐ ┌────┐ ┌────┐ ┌────┐     │
│   │ 12 │ │ 45 │ │ 3  │ │ 1  │     │
│   │ Ex │ │ Ct │ │ Tg │ │ Cn │     │
│   └────┘ └────┘ └────┘ └────┘     │
│                                     │
│   ┌──────────────────────────────┐  │
│   │ ▶ Evidence #142 Processed   │  │
│   │ ▶ Telegram Alert: Center 12 │  │
│   │ ▶ Critical: Match Found     │  │
│   └──────────────────────────────┘  │
│                                     │
│  ─────────────────────────────────  │
│      📱 + 🔵 (Upload FAB)          │
└─────────────────────────────────────┘
```

### 🧠 Evidence Processing Pipeline
```
📄 Upload ──▶ 🔬 OCR (Tesseract) ──▶ 🔍 Watermark Extraction
                │                           │
                ▼                           ▼
         📊 Confidence Score         📝 Paper Attribution
                │                           │
                └───────────┬───────────────┘
                            ▼
                  📋 Forensic Report
                            │
                            ▼
                  🚨 Alert Generation
```

---

## 🤖 AI Service & Community Agents

The `apps/ai-service` Python backend powers the in-app **EXAMSHIELD AI** assistant and the **community agent** system.

- 💬 **Streaming chat** — `POST /chat` streams token-by-token answers (SSE) from the Kilo Gateway LLM (`tencent/hy3:free` by default).
- 🤖 **Community agents** — each agent has its own system prompt, knowledge sources, response style, and citations. Test any agent live from the dashboard *Test Agent* panel (`POST /agents/{id}/test`).
- 📱 **Per-agent Telegram bots** — a deployed agent with its own `botToken` is polled independently and replies **as that agent** in Telegram DMs, using the agent's own LLM provider + knowledge. The global EXAMSHIELD bot keeps answering as EXAMSHIELD AI.
- 🔍 **RAG** — agent replies are grounded in their knowledge base (Supabase pgvector with a local-chunk fallback).

| Capability | Endpoint | Notes |
|------------|----------|-------|
| Chat (stream) | `POST /chat` | SSE token stream |
| Test agent | `POST /agents/{id}/test` | Dashboard "Test Agent" |
| Agent Telegram | polled per `botToken` | Replies as the agent |

---

## 🛠️ Technology Stack

<div align="center">

### 🎨 Frontend
```
┌──────────────────────────────────────────────────────────────┐
│  Next.js 16  │  React 19  │  TypeScript  │  Tailwind CSS    │
│  Framer Motion  │  Lucide Icons  │  @supabase/ssr          │
│  recharts  │  react-simple-maps  │  clsx  │  tailwind-merge │
└──────────────────────────────────────────────────────────────┘
```

### ⚙️ Backend
```
┌──────────────────────────────────────────────────────────────┐
│  Python 3.12  │  Tesseract OCR  │  Supabase (Auth + DB)    │
│  NVIDIA AI  │  Docker  │  Telegram Bot API                 │
└──────────────────────────────────────────────────────────────┘
```

### 🚀 Deployment
```
┌──────────────────────────────────────────────────────────────┐
│  🌐 Vercel (Frontend)          │  🐳 Render (Backend)      │
│  https://faraway-examshield    │  docker + python api       │
│  .vercel.app                   │                            │
└──────────────────────────────────────────────────────────────┘
```

</div>

---

## Performance and scalability

- **Bounded OCR worker pool** — analysis jobs run on a fixed thread pool (`AnalysisWorkerPool`, default 2 workers via `EXAMSHIELD_OCR_WORKERS`); Telegram webhooks and REST uploads submit jobs to the pool so HTTP responses never block on OCR.
- **Read-response caching** — list/read endpoints are cached briefly (`EXAMSHIELD_LIST_CACHE_TTL_SECONDS`) and served with `Cache-Control`, so dashboard polling and Telegram status checks don't re-hit Supabase or Telegram every tick.
- **Streaming chat with a cheap planner** — the assistant runs a separate, short planner LLM call (`EXAMSHIELD_TOOL_PLANNER_TIMEOUT_SECONDS`) only when a tool may be needed, then streams the answer.
- **Token-budget guardrails** — per-request and per-session LLM token ceilings keep one chatty session from exhausting provider quota.
- **Local fallback mode** — without Supabase the backend stores everything as JSON under `apps/api/uploads/evidence/` and uses a local chunk index for agent RAG, so the whole stack runs offline.

## Tech Stack

| Area | Stack |
|------|-------|
| Frontend | Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · Supabase SSR |
| Backend | Python 3.12 · Tesseract + OCR.space · Supabase (Auth / Postgres / Storage / pgvector) · LLM via Kilo Gateway / OpenAI / Anthropic / Grok / Groq / OpenCode Zen · Telegram Bot API |
| Infra | Supabase · Render (Docker) · Vercel · GitHub Actions |
| Testing & tooling | ruff · pytest (backend) |

## 🚀 Getting Started in 60 Seconds

### 🔧 Prerequisites
```
✔ Node.js ≥ 18
✔ Python ≥ 3.12
✔ Docker (optional)
✔ Supabase project
```

### 📦 Installation

<details>
<summary><b>📱 Frontend Setup</b></summary>

```bash
# Navigate to web directory
cd web

# Install dependencies
npm install --legacy-peer-deps

# Create .env.local
cat > .env.local << EOF
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
EXAMSHIELD_API_URL=http://localhost:8790
# EXAMSHIELD_BACKEND_API_KEY=...   # must match backend EXAMSHIELD_API_AUTH_SECRET
EOF

# Start development server
npm run dev
```
</details>

<details>
<summary><b>🐍 Backend Setup</b></summary>

```bash
# Navigate to the AI service directory
cd apps/ai-service

# Create a virtual environment (uv or venv)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Configure environment (see apps/ai-service/.env)
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=your-service-key
export KILO_API_KEY=your-kilo-gateway-key
export EXAMSHIELD_AI_MODEL=tencent/hy3:free

# Run the AI service (SSE chat + Telegram pollers)
python run.py
```
</details>

<details>
<summary><b>🐳 Docker Setup</b></summary>

```bash
# Build and run with Docker
docker build -t examshield-api .
docker run -p 8790:8790 examshield-api
```
</details>

**Environment variables**

| Variable | Required | Purpose |
|----------|----------|---------|
| `SUPABASE_URL` | yes* | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | yes* | Supabase service-role key (backend fallback when RLS context is unavailable) |
| `KILO_API_KEY` | yes* | Kilo Gateway API key (AI chat) |
| `EXAMSHIELD_AI_CORS_ORIGIN` | yes* | Frontend origin allowed by CORS |
| `EXAMSHIELD_PUBLIC_URL` | no | Public backend URL (Telegram webhook) |
| `TELEGRAM_BOT_TOKEN` | no | Global EXAMSHIELD Telegram bot |
| `TELEGRAM_WEBHOOK_SECRET` | no | Telegram webhook secret |
| `EXAMSHIELD_AI_MODEL` | no | Chat model (default `tencent/hy3:free`) |
| `OCR_SPACE_API_KEY` | no | Enables the OCR.space engine |
| `EXAMSHIELD_OCR_WORKERS` | no | OCR worker-pool size (default 2) |

\* Required for production (Supabase-backed) deployments; without them the backend runs in offline mode.

The full variable list is in [`render.yaml`](render.yaml). See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for setup details.

## Testing & CI

```bash
# Backend (ruff + pytest)
cd apps/ai-service && pip install -r requirements.txt && ruff check . && pytest tests -q

# Frontend (typecheck + build)
cd web && npm ci && npx tsc --noEmit && npm run build
```

CI runs on GitHub Actions (`.github/workflows/quality-gate.yml`) on every push/PR to `main`:

- **Backend job** (from `apps/ai-service`): `ruff check .` → `pytest tests -q`.
- **Frontend job** (from `web`): `npm ci` → `npx tsc --noEmit` → `npm run build`.

### 🌐 Environment Variables

<details>
<summary><b>Vercel (Frontend)</b></summary>

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Public anon key |

</details>

<details>
<summary><b>Render (Backend)</b></summary>

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Service role key |
| `KILO_API_KEY` | ⚠️ | For AI service (Kilo Gateway) |
| `TELEGRAM_BOT_TOKEN` | ⚠️ | Telegram bot |
| `TELEGRAM_WEBHOOK_SECRET` | ⚠️ | Webhook secret |
| `TELEGRAM_CHAT_ID` | ⚠️ | Chat ID |
| `EXAMSHIELD_AI_CORS_ORIGIN` | ✅ | Frontend URL |
| `EXAMSHIELD_API_AUTH_SECRET` | ⚠️ | Shared secret protecting the backend API (audit §2.2); the frontend proxy sends it as `X-Examshield-Api-Key`. Required in production — when unset the API is reachable anonymously with a startup warning. |
| `EXAMSHIELD_PUBLIC_URL` | ✅ | Backend URL |
| `EXAMSHIELD_AI_MODEL` | ⚠️ | Chat model (Kilo Gateway, e.g. `tencent/hy3:free`) |
| `EXAMSHIELD_AI_FALLBACK_MODELS` | ⚠️ | Comma-separated fallback models |
| `EXAMSHIELD_AI_PLANNER_MODEL` | ⚠️ | Model used for tool planning |

</details>

---

## 📡 Deployment

<div align="center">

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   🚀 DEPLOYMENT PIPELINE                                            │
│                                                                     │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌────────┐   │
│   │  GIT     │────▶│  VERCEL  │────▶│  LIVE    │────▶│  TEST  │   │
│   │  PUSH    │     │  BUILD   │     │  SITE    │     │  PASS  │   │
│   └──────────┘     └──────────┘     └──────────┘     └────────┘   │
│         │                                                            │
│         ▼                                                            │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐                   │
│   │  RENDER  │────▶│  DOCKER  │────▶│  BACKEND │                   │
│   │  DEPLOY  │     │  BUILD   │     │  API     │                   │
│   └──────────┘     └──────────┘     └──────────┘                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

</div>

### 🎯 Quick Deploy

EXAMSHIELD runs as one Python backend on Render (Docker) and a Next.js frontend on Vercel, with Supabase for auth, database, storage, and pgvector. For the full walkthrough (Supabase schema, Render blueprint, Vercel env, Telegram webhook), see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

```bash
# Deploy frontend to Vercel
cd web && npx vercel --prod

# Deploy backend to Render
# (Configure via render.yaml or dashboard)
```

**Live Demo:** [https://faraway-examshield.vercel.app](https://faraway-examshield.vercel.app)

---

## 🔒 Security Architecture

<table>
<tr>
<th>Layer</th>
<th>Implementation</th>
<th>Status</th>
</tr>
<tr>
<td>🔐 Authentication</td>
<td>Supabase JWT + Cookie Sessions</td>
<td>✅ Active</td>
</tr>
<tr>
<td>🛡️ Route Protection</td>
<td>Next.js Middleware (Edge Runtime)</td>
<td>✅ Active</td>
</tr>
<tr>
<td>🔑 OAuth Providers</td>
<td>Google + GitHub SSO</td>
<td>✅ Active</td>
</tr>
<tr>
<td>📝 Audit Logging</td>
<td>Supabase Activity Tracking</td>
<td>✅ Active</td>
</tr>
<tr>
<td>🔒 Session Management</td>
<td>Secure, HTTP-only Cookies</td>
<td>✅ Active</td>
</tr>
<tr>
<td>🚫 Rate Limiting</td>
<td>Planned (API Gateway)</td>
<td>🔄 Planned</td>
</tr>
<tr>
<td>🧪 Security Audits</td>
<td>Regular Review Cycle</td>
<td>🔄 Planned</td>
</tr>
</table>

---

## 📈 Roadmap

```
Q2 2026                    Q3 2026                    Q4 2026
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ ✅ Auth Complete  │      │ 🔄 AI Enhance    │      │ 🔄 Enterprise    │
│ ✅ Dashboard V1   │      │ 🔄 Performance   │      │ 🔄 Compliance    │
│ ✅ Mobile V1      │      │ 🔄 Analytics V2  │      │ 🔄 Scale        │
│ ✅ Deploy V1      │      │ 🔄 Monitoring    │      │ 🔄 SLA           │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

- **[x] Phase 1: Foundation** — Auth, Dashboard, Mobile, Deploy ✅
- **[ ] Phase 2: Intelligence** — Advanced AI, Analytics, Monitoring
- **[ ] Phase 3: Enterprise** — Compliance, SLA, Scale

---

## 🤝 Contributing

<div align="center">

[![PRs Welcome](https://img.shields.io/badge/PRs-WELCOME-22c55e?style=for-the-badge)](https://github.com/risuhfoundry/Faraway-examshield/pulls)
[![Issues](https://img.shields.io/badge/Issues-OPEN-6366f1?style=for-the-badge)](https://github.com/risuhfoundry/Faraway-examshield/issues)
[![Forks](https://img.shields.io/github/forks/risuhfoundry/Faraway-examshield?style=for-the-badge&color=22c55e)](https://github.com/risuhfoundry/Faraway-examshield/forks)
[![Stars](https://img.shields.io/github/stars/risuhfoundry/Faraway-examshield?style=for-the-badge&color=f59e0b)](https://github.com/risuhfoundry/Faraway-examshield/stargazers)

</div>

1. 🍴 **Fork** the repository
2. 🌿 **Create** a feature branch (`git checkout -b feature/amazing`)
3. 💻 **Commit** your changes (`git commit -m 'feat: add something amazing'`)
4. 📤 **Push** to the branch (`git push origin feature/amazing`)
5. 🎯 **Open** a Pull Request

---

## 📜 License

```
EXAMSHIELD — Proprietary Software
Copyright © 2026 Faraway Technologies
All rights reserved.
```

---

<div align="center">
  <sub>Built with ❤️, 🦀, and ☕ for academic integrity</sub>
  <br/>
  <sub>EXAMSHIELD — The new standard in examination security</sub>
  <br/><br/>
  <img src="https://img.shields.io/badge/END_OF_README-🔒_SYSTEM_SECURE-000000?style=for-the-badge" />
</div>
