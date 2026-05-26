"""
FastAPI application entry point — Phase 5 hardened startup.

Startup sequence:
  1. Preload embedding model (warm-start — eliminates 20s cold-start latency)
  2. Mount CORS middleware
  3. Mount routes
  4. Mount static frontend (if present)

Embedding preload is non-blocking on server startup errors:
  if SentenceTransformer is unavailable, fallback stub is used silently.
"""

import logging
import time
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.query import router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Deterministic Embedded AI Engine",
    description="Hardware-safe deterministic reasoning engine for embedded systems.",
    version="2.0.0",
)

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP EVENT — preload embedding model before first request
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    t0 = time.time()
    logger.info("[STARTUP] Initializing Deterministic Embedded AI Engine v2.0.0...")

    try:
        from app.services.embeddings import preload, get_status
        preload()
        status = get_status()
        elapsed = round((time.time() - t0) * 1000, 1)
        if status["fallback_mode"]:
            logger.warning(
                f"[STARTUP] Embedding model in FALLBACK mode "
                f"(semantic search disabled). Startup: {elapsed}ms"
            )
        else:
            logger.info(
                f"[STARTUP] Embedding model ready — "
                f"load: {status['load_time_ms']}ms | total startup: {elapsed}ms"
            )
    except Exception as e:
        logger.error(f"[STARTUP] Embedding preload failed: {e} — server continues in degraded mode.")

    try:
        from app.services.conversation_state import get_session
        logger.info("[STARTUP] Conversation state store initialized.")
    except Exception as e:
        logger.error(f"[STARTUP] Conversation store init failed: {e}")

    logger.info("[STARTUP] Orchestration engine ready.")


# ─────────────────────────────────────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(router)

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
def health_check():
    try:
        from app.services.embeddings import get_status
        emb_status = get_status()
    except Exception:
        emb_status = {"model_ready": False}

    return {
        "status": "ok",
        "engine": "Deterministic Embedded AI Engine",
        "version": "2.0.0",
        "embedding_ready": emb_status.get("model_ready", False),
        "embedding_fallback": emb_status.get("fallback_mode", True),
        "embedding_load_ms": emb_status.get("load_time_ms", 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STATIC FRONTEND (optional)
# ─────────────────────────────────────────────────────────────────────────────
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_path = os.path.join(os.path.dirname(base_dir), "frontend")

if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
