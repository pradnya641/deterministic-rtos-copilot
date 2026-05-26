"""
Embedding Lifecycle Manager — Phase 5 Hardened Singleton.

Architectural guarantees:
  - Model loaded ONCE at server startup via preload()
  - Shared across rag.py, knowledge.py, validator.py
  - model_ready flag prevents usage before load is complete
  - Lazy fallback stub returned if SentenceTransformer unavailable
  - Preload timing metrics exposed via get_status()
  - No duplicate SentenceTransformer instantiation anywhere

Usage (in rag.py, knowledge.py, validator.py):
    from app.services.embeddings import get_model, model_ready

Usage (in main.py startup):
    from app.services.embeddings import preload
    preload()
"""

import time
import logging
import threading

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Internal state
# ─────────────────────────────────────────────────────────────────────────────
_model = None
_model_ready = False
_load_time_ms: float = 0.0
_load_error: str | None = None
_load_lock = threading.Lock()

MODEL_NAME = "all-MiniLM-L6-v2"


# ─────────────────────────────────────────────────────────────────────────────
# Fallback stub — used when sentence_transformers is unavailable
# ─────────────────────────────────────────────────────────────────────────────
class _FallbackModel:
    """Zero-vector stub — lets the server boot even without sentence_transformers."""
    def encode(self, sentences, **kwargs):
        try:
            import numpy as np
            n = len(sentences) if isinstance(sentences, list) else 1
            return np.zeros((n, 384), dtype="float32")
        except ImportError:
            return [[0.0] * 384] * (len(sentences) if isinstance(sentences, list) else 1)

    def __repr__(self):
        return "FallbackModel(zero-vectors)"


# ─────────────────────────────────────────────────────────────────────────────
# PRELOAD — called once at server startup
# ─────────────────────────────────────────────────────────────────────────────
def preload() -> None:
    """
    Load the SentenceTransformer model at server startup.
    Idempotent — safe to call multiple times.
    Logs preload timing. Sets model_ready = True on success.
    """
    global _model, _model_ready, _load_time_ms, _load_error

    with _load_lock:
        if _model_ready:
            return   # Already loaded

        t0 = time.time()
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"[EMBEDDINGS] Loading model '{MODEL_NAME}'...")
            _model = SentenceTransformer(MODEL_NAME)
            _load_time_ms = round((time.time() - t0) * 1000, 1)
            _model_ready = True
            logger.info(f"[EMBEDDINGS] Model ready in {_load_time_ms}ms.")
        except ImportError:
            _load_time_ms = round((time.time() - t0) * 1000, 1)
            _load_error = "sentence_transformers not installed"
            _model = _FallbackModel()
            _model_ready = True   # Fallback is "ready"
            logger.warning(
                f"[EMBEDDINGS] sentence_transformers not available — "
                f"using zero-vector fallback. Semantic search disabled."
            )
        except Exception as e:
            _load_time_ms = round((time.time() - t0) * 1000, 1)
            _load_error = str(e)
            _model = _FallbackModel()
            _model_ready = True
            logger.error(f"[EMBEDDINGS] Model load failed ({e}) — using fallback.")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ACCESSORS
# ─────────────────────────────────────────────────────────────────────────────
def get_model():
    """
    Return the singleton model instance.
    Triggers a lazy preload if not already loaded (warm path).
    """
    if not _model_ready:
        preload()
    return _model


def model_ready() -> bool:
    return _model_ready


def get_status() -> dict:
    """Return embedding lifecycle metrics for observability."""
    return {
        "model_name":    MODEL_NAME,
        "model_ready":   _model_ready,
        "load_time_ms":  _load_time_ms,
        "fallback_mode": isinstance(_model, _FallbackModel),
        "load_error":    _load_error,
    }


# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD COMPATIBILITY SHIM
# `model` was previously imported directly as a module-level instance.
# Existing code that does `from .embeddings import model` still works.
# ─────────────────────────────────────────────────────────────────────────────
class _LazyModelProxy:
    """
    Proxy that behaves like SentenceTransformer but loads lazily on first use.
    Allows `from .embeddings import model` to remain valid everywhere.
    """
    def encode(self, *args, **kwargs):
        return get_model().encode(*args, **kwargs)

    def __repr__(self):
        return f"LazyModelProxy(ready={_model_ready})"


model = _LazyModelProxy()
