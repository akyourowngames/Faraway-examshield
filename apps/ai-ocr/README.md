# EXAMSHIELD OCR Worker

Legacy standalone Python OCR service. The preferred runtime is now the unified AI service in `apps/ai-service`, which exposes the same OCR analyzer at `POST /ocr/analyze` so chat tools and OCR share one Python microservice.

## Run

```powershell
python worker.py
```

The service listens on `http://127.0.0.1:8765` by default.

## Endpoint

```txt
POST /analyze
```

Send raw image bytes with `Content-Type: image/jpeg` or `image/png`.

Response:

```json
{
  "status": "completed",
  "confidence": 96,
  "text": "Question 1 ...",
  "processingTimeMs": 841
}
```

The worker only performs OCR.

## OCR Candidate Scoring

The worker runs a small set of Tesseract page segmentation modes and selects the strongest text candidate using generic OCR quality signals. It no longer filters output by exam keywords or question-pattern rules; if Tesseract extracts text, the response returns that text for the attribution pipeline to evaluate.
