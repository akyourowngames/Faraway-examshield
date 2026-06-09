# EXAMSHIELD Web

Next.js frontend for EXAMSHIELD.

The frontend contains no evidence database, OCR worker, or analysis backend. Its route handlers proxy to the single unified Python API.

## Run

```powershell
$env:EXAMSHIELD_API_URL="http://127.0.0.1:8790"
npm run dev
```

For Vercel and Render setup, see [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).
