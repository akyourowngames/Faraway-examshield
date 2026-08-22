"""Placeholder realtime router.

The stdlib transport has no dedicated realtime endpoint; this router exists so
the FastAPI app has a stable mount point for future realtime additions without
changing ``app.py``. It is intentionally empty.
"""
from fastapi import APIRouter

router = APIRouter()
