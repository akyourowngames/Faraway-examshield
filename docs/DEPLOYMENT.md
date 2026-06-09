# Deploy EXAMSHIELD with Supabase, Render, and Vercel

EXAMSHIELD uses one Python backend process on Render. That process owns OCR, evidence, analysis jobs, attribution, alerts, AI chat, and optional Telegram webhook ingestion. Vercel hosts the Next.js frontend and proxies its backend routes to Render. Supabase stores all backend documents and uploaded evidence files.

## Architecture

```txt
Browser -> Vercel Next.js -> Render unified Python API -> Supabase
                                              |
                                              +-> NVIDIA NIM
                                              +-> Tesseract OCR
Telegram webhook -----------------------------+
```

Do not put the Supabase service-role key or NVIDIA key in Vercel. They belong only on Render.

## 1. Create Supabase storage

1. Create a Supabase project.
2. Open **SQL Editor**.
3. Run [`supabase/schema.sql`](../supabase/schema.sql).
4. Open **Project Settings > API** and copy:
   - Project URL
   - `service_role` key

The SQL creates:

- `public.examshield_documents`: private JSON document storage for evidence, jobs, reports, alerts, activity, and the registry.
- `evidence-files`: private Supabase Storage bucket for uploaded images and PDFs.

The unified API uses the service-role key server-side, so no public RLS policy is required.

## 2. Deploy the unified API on Render

This repo includes [`Dockerfile`](../Dockerfile) because OCR needs the Tesseract system package. It also includes [`render.yaml`](../render.yaml).

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint** and select the repository.
3. Confirm the `examshield-api` free web service.
4. Set these required environment variables:

| Variable | Value |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key |
| `NVIDIA_API_KEY` | NVIDIA NIM API key |
| `EXAMSHIELD_AI_CORS_ORIGIN` | Your Vercel production URL, or `*` during setup |

Render supplies `PORT`. The server automatically binds to `0.0.0.0` and that port.

After deploy, open:

```txt
https://YOUR-RENDER-SERVICE.onrender.com/health
```

Confirm that the response contains:

```json
{
  "status": "ok",
  "storage": "supabase",
  "ocr": {
    "endpoint": "/ocr/analyze"
  }
}
```

Render free web services spin down after 15 minutes without inbound traffic and have an ephemeral local filesystem. Supabase is therefore required for durable evidence and database state.

## 3. Optional Telegram webhook

No separate Telegram agent process is needed. Add these Render variables:

| Variable | Value |
| --- | --- |
| `EXAMSHIELD_PUBLIC_URL` | Render service URL without a trailing slash |
| `TELEGRAM_BOT_TOKEN` | BotFather token |
| `TELEGRAM_WEBHOOK_SECRET` | A long random secret |
| `TELEGRAM_CHAT_ID` | Optional allowed chat/group ID |

On every API start, EXAMSHIELD registers:

```txt
https://YOUR-RENDER-SERVICE.onrender.com/telegram/webhook
```

Telegram messages and supported media then enter the same evidence/OCR pipeline.

## 4. Deploy the frontend on Vercel from terminal

Install or update the CLI:

```powershell
npm install --global vercel
```

From the repository root, link the `web` project:

```powershell
vercel link --cwd web
```

Add the Render URL as a server-side variable for all environments:

```powershell
vercel env add EXAMSHIELD_API_URL production --cwd web
vercel env add EXAMSHIELD_API_URL preview --cwd web
vercel env add EXAMSHIELD_API_URL development --cwd web
```

Enter this value when prompted:

```txt
https://YOUR-RENDER-SERVICE.onrender.com
```

Deploy production:

```powershell
vercel deploy --prod --cwd web
```

The browser calls same-origin Vercel routes such as `/evidence`, `/analysis/jobs`, and `/chat`. Those routes stream or proxy to the single Render API using `EXAMSHIELD_API_URL`.

## 5. Verify the aligned deployment

1. Open the Vercel URL.
2. Open **Investigation Workspace**.
3. Upload a JPG or PNG containing clear printed text.
4. Start analysis.
5. Confirm OCR completes and the item appears in **Evidence Center**.
6. Open the Render `/health` endpoint and confirm `"storage": "supabase"`.
7. Restart or redeploy Render, then confirm the evidence still appears. This proves data is coming from Supabase rather than Render's local filesystem.

## Local development

Start the one backend command:

```powershell
python apps/ai-service/service.py
```

Then start the frontend:

```powershell
cd web
$env:EXAMSHIELD_API_URL="http://127.0.0.1:8790"
npm run dev
```

Without Supabase variables, the backend deliberately falls back to local JSON/files for offline development. Production health must report `supabase`.

## Routing rule

AI tool selection remains model-and-schema driven through the registered tool schemas. OCR attribution compares extracted data with the registry. Do not add keyword, regex, or hardcoded prompt-routing shortcuts.
