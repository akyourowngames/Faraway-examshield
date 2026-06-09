# EXAMSHIELD Unified API

The single Python backend for EXAMSHIELD.

It owns:

- Evidence upload, list, and detail endpoints
- OCR using Tesseract
- Analysis jobs, attribution, reports, and alerts
- NVIDIA NIM chat and schema-driven tool routing
- Supabase document and file storage
- Optional Telegram webhook ingestion

## Run

```powershell
python apps/ai-service/service.py
```

Default local URL: `http://127.0.0.1:8790`

## Main endpoints

- `GET /health`
- `GET /tools`
- `GET /evidence`
- `GET /evidence/{id}`
- `GET /alerts`
- `POST /evidence/upload`
- `POST /analysis/jobs`
- `POST /analysis/jobs/{id}/process`
- `POST /ocr/analyze`
- `POST /chat`
- `POST /telegram/events`
- `POST /telegram/webhook`
- `POST /demo/reset`

## Production

Production uses Supabase when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set. Without them, the API falls back to local JSON and files for offline development.

See [`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md).

AI tool selection remains model-and-schema driven. Do not add keyword, regex, or hardcoded prompt-routing shortcuts.
