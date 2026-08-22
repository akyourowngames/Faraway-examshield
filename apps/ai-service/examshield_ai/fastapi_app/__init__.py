"""FastAPI transport for the ExamShield AI service.

This package reuses the same business cores as the stdlib
``examshield_ai.server`` transport while exposing them through a FastAPI/uvicorn
ASGI server. The stdlib server remains available as a fallback via
``EXAMSHIELD_HTTP_MODE=stdlib``.
"""
