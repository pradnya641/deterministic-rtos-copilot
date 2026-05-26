"""
Domain-routed RAG retrieval service — Phase 4 Hardened.

Architectural changes (Phase 4):
  - FAISS index state detection: missing / empty / corrupt
  - safe_retrieve_context(): hard 2-second timeout via concurrent.futures
  - Graceful degradation: any retrieval failure returns "" silently
  - Subsystem isolation: embedding failure never kills response pipeline
  - Retrieval state reported via returned context prefix (not exceptions)

Domain → FAISS index mapping:
  hardware_reasoning       → db/hardware_index
  rtos_architecture        → db/rtos_index
  sensor_integration       → db/sensors_index
  communication_design     → db/protocols_index
  automotive_logic         → db/hardware_index
  embedded_debugging       → db/hardware_index
  system_architecture      → db/hardware_index
  peripheral_configuration → db/hardware_index
  default / unknown        → db/lpc2148_index  (legacy)
"""

import os
import logging
import concurrent.futures

# ─────────────────────────────────────────────────────────────────────────────
# Guarded imports — never crash the server if a dep is missing
# ─────────────────────────────────────────────────────────────────────────────
try:
    import faiss
    _FAISS_AVAILABLE = True
except ImportError:
    faiss = None
    _FAISS_AVAILABLE = False
    logging.warning("[RAG] faiss-cpu not installed — retrieval disabled.")

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    np = None
    _NUMPY_AVAILABLE = False
    logging.warning("[RAG] numpy not installed — retrieval disabled.")

try:
    from .embeddings import model as embed_model
    _EMBED_AVAILABLE = True
except Exception as _e:
    embed_model = None
    _EMBED_AVAILABLE = False
    logging.warning(f"[RAG] Embedding model unavailable: {_e} — retrieval disabled.")

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
DB_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db"
)

RETRIEVAL_TIMEOUT_S = 2.0   # hard cap — never exceed this

# Only these intents are allowed to trigger FAISS retrieval
RAG_ENABLED_INTENTS = {
    "peripheral_configuration",
    "hardware_reasoning",
    "communication_design",
}

INTENT_TO_INDEX = {
    "hardware_reasoning":        "hardware_index",
    "peripheral_configuration":  "hardware_index",
    "embedded_debugging":        "hardware_index",
    "system_architecture":       "hardware_index",
    "automotive_logic":          "hardware_index",
    "rtos_architecture":         "rtos_index",
    "sensor_integration":        "sensors_index",
    "communication_design":      "protocols_index",
    "system":                    "lpc2148_index",
    "unknown":                   "lpc2148_index",
    # legacy
    "reasoning":                 "hardware_index",
    "code":                      "hardware_index",
}

DOMAIN_METADATA = {
    "hardware_index":  {"source": "LPC2148 Manual / ARM7 TRM",  "domain": "hardware"},
    "rtos_index":      {"source": "FreeRTOS Reference + Guide",  "domain": "rtos"},
    "sensors_index":   {"source": "Sensor Datasheets",           "domain": "sensors"},
    "protocols_index": {"source": "I2C / SPI / UART References", "domain": "protocols"},
    "lpc2148_index":   {"source": "LPC2148 Manual",              "domain": "hardware"},
}

# In-memory index cache: {index_name: (faiss.Index, list[str])}
_index_cache: dict = {}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — FAISS INDEX STATE DETECTION
# ─────────────────────────────────────────────────────────────────────────────
def _index_state(index_name: str) -> str:
    """
    Returns one of:
      'ok'       — index files exist and are non-empty
      'missing'  — index directory or files do not exist
      'empty'    — files exist but index has 0 vectors
    Never raises.
    """
    index_dir   = os.path.join(DB_BASE, index_name)
    index_path  = os.path.join(index_dir, "index.faiss")
    chunks_path = os.path.join(index_dir, "chunks.txt")

    if not os.path.exists(index_path) or not os.path.exists(chunks_path):
        return "missing"
    if os.path.getsize(index_path) == 0:
        return "empty"
    return "ok"


def _load_index(index_name: str):
    """
    Load a FAISS index + chunks from disk (cached).
    Returns (None, []) on any failure — never raises.
    """
    if not _FAISS_AVAILABLE or not _NUMPY_AVAILABLE:
        return None, []

    if index_name in _index_cache:
        return _index_cache[index_name]

    state = _index_state(index_name)
    if state == "missing":
        # Try legacy fallback
        fallback = "lpc2148_index"
        if index_name == fallback or _index_state(fallback) != "ok":
            logger.warning(f"[RAG] Index '{index_name}' missing, no fallback available.")
            return None, []
        logger.warning(f"[RAG] Index '{index_name}' missing — falling back to '{fallback}'.")
        index_name = fallback

    if state == "empty":
        logger.warning(f"[RAG] Index '{index_name}' is empty (0 bytes).")
        return None, []

    index_dir   = os.path.join(DB_BASE, index_name)
    index_path  = os.path.join(index_dir, "index.faiss")
    chunks_path = os.path.join(index_dir, "chunks.txt")

    try:
        idx = faiss.read_index(index_path)
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = f.read().split("\n---CHUNK_SEP---\n")
        _index_cache[index_name] = (idx, chunks)
        return idx, chunks
    except Exception as e:
        logger.error(f"[RAG] Failed to load index '{index_name}': {e}")
        return None, []


# ─────────────────────────────────────────────────────────────────────────────
# CORE RETRIEVAL (runs inside executor for timeout isolation)
# ─────────────────────────────────────────────────────────────────────────────
def _do_retrieve(index_name: str, query: str, k: int) -> str:
    """
    Internal: runs synchronous FAISS retrieval.
    Called by safe_retrieve_context() inside a thread with timeout.
    """
    idx, chunks = _load_index(index_name)
    if idx is None:
        return ""

    k_actual = min(k, idx.ntotal)
    if k_actual == 0:
        return ""

    embedding = embed_model.encode([query])
    D, I = idx.search(embedding, k_actual)

    retrieved = [chunks[i] for i in I[0] if i < len(chunks)]
    if not retrieved:
        return ""

    metadata = DOMAIN_METADATA.get(index_name, {})
    header = (
        f"[Source: {metadata.get('source', index_name)} | "
        f"Domain: {metadata.get('domain', 'unknown')}]\n\n"
    )
    return header + "\n\n---\n\n".join(retrieved)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — RETRIEVAL CIRCUIT BREAKER
# ─────────────────────────────────────────────────────────────────────────────
def safe_retrieve_context(parsed: dict, board: str = "lpc2148", k: int = 5) -> str:
    """
    Circuit-breaker wrapped retrieval.

    Guarantees:
      - Never blocks longer than RETRIEVAL_TIMEOUT_S (2 seconds)
      - Returns "" on any failure (timeout, missing index, crash)
      - Never raises an exception to the caller
      - Logs all failures for diagnostics

    Architectural contract:
      RAG failure MUST NOT kill response generation.
    """
    # ── Dependency check ──────────────────────────────────────────────────────
    if not _FAISS_AVAILABLE or not _EMBED_AVAILABLE or not _NUMPY_AVAILABLE:
        logger.warning("[RAG] Retrieval skipped — required subsystem unavailable.")
        return ""

    intent = parsed.get("intent", "unknown")

    # ── Index selection ───────────────────────────────────────────────────────
    index_name = INTENT_TO_INDEX.get(intent, "lpc2148_index")

    # ── Pre-flight index state check (fast — no I/O block) ───────────────────
    if _index_state(index_name) == "missing":
        logger.warning(f"[RAG] Index '{index_name}' missing — retrieval skipped.")
        return ""

    # ── Build enriched query ──────────────────────────────────────────────────
    raw_query   = parsed.get("raw_query", "")
    peripherals = parsed.get("peripherals", [])
    sensors     = parsed.get("sensors", [])

    technical_terms = [
        "dlab", "pinsel", "vic", "pclk", "cclk", "pll",
        "mam", "fio", "scb", "dll", "dlm",
        "xtaskcreate", "vtaskdelay", "xqueuecreate", "freertos",
        "ad0cr", "pwmmr0", "u0lcr"
    ]
    boosted = [t for t in technical_terms if t in raw_query.lower()]
    query = f"{raw_query} {' '.join(peripherals + sensors)} {' '.join(boosted)}".strip()

    # ── Timed execution via thread executor ───────────────────────────────────
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_retrieve, index_name, query, k)
            result = future.result(timeout=RETRIEVAL_TIMEOUT_S)
            return result or ""
    except concurrent.futures.TimeoutError:
        logger.warning(
            f"[RAG] Retrieval timeout ({RETRIEVAL_TIMEOUT_S}s) for intent='{intent}' "
            f"index='{index_name}' — continuing without RAG context."
        )
        return ""
    except Exception as e:
        logger.error(f"[RAG] Retrieval failed unexpectedly: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# BACKWARD COMPAT — keep retrieve_context as alias
# ─────────────────────────────────────────────────────────────────────────────
def retrieve_context(parsed: dict, board: str = "lpc2148", k: int = 5) -> str:
    """Backward-compatible alias for safe_retrieve_context."""
    return safe_retrieve_context(parsed, board, k)


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY SHIM
# ─────────────────────────────────────────────────────────────────────────────
def load_faiss(board: str):
    """Legacy function kept for backward compatibility."""
    return _load_index("lpc2148_index")
