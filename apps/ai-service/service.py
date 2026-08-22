from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    """Entrypoint for the ExamShield AI backend (FastAPI/uvicorn ASGI)."""
    import uvicorn

    uvicorn.run(
        "examshield_ai.fastapi_app.app:app",
        host=os.environ.get("EXAMSHIELD_AI_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT") or os.environ.get("EXAMSHIELD_AI_PORT", "8790")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
