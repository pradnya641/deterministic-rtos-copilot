"""
Fuzzy Query Normalizer — Deterministic Embedded Firmware Copilot.

Architectural purpose:
  Allow spelling mistakes and embedded shorthand to reach the correct
  intent path without weakening semantic precision.

Deterministic contract:
  - Uses ONLY the existing sentence-transformers singleton from embeddings.py.
  - NO new NLP library dependencies (no rapidfuzz, no difflib fuzzy).
  - Hard threshold (NORMALIZE_THRESHOLD = 0.82) prevents hallucinated rewrites.
  - If the embedding model is in fallback mode (zero vectors), normalization
    is bypassed silently and the raw query passes through unchanged.
  - The canonical form is APPENDED to the raw query (not replaced), preserving
    the original intent signals for the downstream parser.

Validation strategy:
  - normalize() NEVER changes the intent if cosine similarity < threshold.
  - normalize() NEVER rewrites hardware register names or numeric parameters.
  - normalize() NEVER raises exceptions to caller — returns raw query on any failure.

RTOS implications:
  - None. This module only transforms text strings. No RTOS object manipulation.

Compile implications:
  - None. Normalization happens before any code synthesis.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Cosine similarity threshold above which normalization is applied.
# 0.82 is tight enough to avoid false positives on genuinely different intents.
# Example: "add dma" (0.91 vs "add DMA-ready architecture") → rewrite.
#          "add debug" (0.61 vs "add DMA-ready architecture") → pass through.
NORMALIZE_THRESHOLD = 0.82

# Pattern that protects hardware register names and numeric parameters from
# being altered by the normalization (append-only, but defensive).
_REGISTER_PATTERN = re.compile(
    r'\b(AD0CR|PINSEL[01]|PWMMR\d|PWMPCR|PWMTCR|U[01][A-Z]{2,5}|'
    r'VICVect\w+|IO[01][A-Z]+|T[01]TC|CAN\d\w+|S0SP\w+|WD\w+|'
    r'0x[0-9A-Fa-f]+|\d+MHz|\d+kHz|\d+baud)\b',
    re.IGNORECASE
)


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDED SHORTHAND CORPUS
# ─────────────────────────────────────────────────────────────────────────────
# Format: (shorthand_phrase, canonical_embedded_phrase)
#
# Design rules:
#   1. Shorthand covers common typos, abbreviations, and spoken shorthand.
#   2. Canonical form uses full embedded engineering terminology.
#   3. Corpus is closed and bounded — not dynamically expandable.
#   4. Each pair must have a clear semantic relationship with no ambiguity.

NORMALIZATION_CORPUS: list[tuple[str, str]] = [
    # Queue operations
    ("freertos q",                          "FreeRTOS queue"),
    ("uart isr usng q",                     "UART ISR using queue"),
    ("add q",                               "increase queue depth"),
    ("make q bigger",                       "increase queue depth"),
    ("larger q",                            "increase queue depth"),
    ("bigger queue",                        "increase queue depth"),
    ("deeper queue",                        "increase queue depth"),
    ("increase q",                          "increase queue depth"),
    ("make queue bigger",                   "increase queue depth"),
    ("incr q",                              "increase queue depth"),

    # Overflow protection
    ("add ovflow prot",                     "add queue overflow protection"),
    ("overflow prot",                       "add queue overflow protection"),
    ("add ovflw",                           "add queue overflow protection"),
    ("monitor q",                           "add queue overflow protection"),
    ("queue watermrk",                      "add queue overflow protection"),
    ("add overflow detect",                 "add queue overflow protection"),

    # ISR conversion
    ("swap pollin with isr",                "convert polling to interrupt-driven"),
    ("rm polling",                          "remove polling loop replace with interrupt"),
    ("remove polling",                      "convert polling to interrupt-driven"),
    ("replace polling",                     "convert polling to interrupt-driven"),
    ("interrupt driven",                    "convert polling to interrupt-driven"),
    ("use isr insted",                      "convert polling to interrupt-driven"),
    ("make interrupt driven",               "convert polling to interrupt-driven"),
    ("reduce cpu usage",                    "convert polling to interrupt-driven"),

    # DMA
    ("add dma",                             "add DMA-ready architecture"),
    ("dma rdy",                             "add DMA-ready architecture"),
    ("dma path",                            "add DMA-ready architecture"),
    ("dma ready",                           "add DMA-ready architecture"),
    ("use dma",                             "add DMA-ready architecture"),

    # Latency optimization
    ("optmize latency",                     "optimize task latency and priorities"),
    ("optimze latency",                     "optimize task latency and priorities"),
    ("reduce latency",                      "optimize task latency and priorities"),
    ("faster resp",                         "optimize task latency and priorities"),
    ("lower jitter",                        "optimize task latency and priorities"),
    ("lower latency",                       "optimize task latency and priorities"),

    # Watchdog
    ("add wdg",                             "add watchdog timer"),
    ("add wdt",                             "add watchdog timer"),
    ("add watchdg",                         "add watchdog timer"),
    ("watchdog",                            "add watchdog timer"),

    # Retry logic
    ("add rtry",                            "add retry logic"),
    ("retry logic",                         "add retry logic"),
    ("add retries",                         "add retry logic"),

    # Stack
    ("reduce stk",                          "reduce task stack usage"),
    ("smaller stk",                         "reduce task stack usage"),
    ("less stack",                          "reduce task stack usage"),

    # Priority
    ("change prio",                         "change task priority"),
    ("higher prio",                         "increase task priority"),
    ("lower prio",                          "decrease task priority"),
    ("rms optimize",                        "optimize priorities for RMS scheduling"),

    # Mutex / CAN / LCD additions
    ("add mutex",                           "add mutex safety"),
    ("remove can",                          "remove CAN architecture"),
    ("use lcd",                             "display UART on LCD"),

    # Generation requests (first-turn)
    ("uart isr pipeln",                     "generate UART ISR pipeline"),
    ("gen uart isr",                        "generate UART ISR pipeline"),
    ("uart isr q",                          "generate UART ISR queue pipeline"),
    ("gps gsm",                             "generate GPS GSM telemetry architecture"),
    ("can telm",                            "generate CAN bus telemetry architecture"),
    ("adc filtr",                           "generate ADC acquisition and filtering pipeline"),
]


# Lazy-loaded embeddings for the corpus
_corpus_embeddings = None
_corpus_texts: list[str] = []


def _load_corpus_embeddings() -> Optional[object]:
    """
    Lazy-load and cache corpus embeddings.
    Returns the numpy embedding array, or None if unavailable.
    """
    global _corpus_embeddings, _corpus_texts

    if _corpus_embeddings is not None:
        return _corpus_embeddings

    try:
        from app.services.embeddings import get_model, model_ready
        if not model_ready():
            return None

        m = get_model()
        _corpus_texts = [pair[0] for pair in NORMALIZATION_CORPUS]
        _corpus_embeddings = m.encode(_corpus_texts, convert_to_tensor=False)
        logger.debug(
            f"[NORMALIZER] Corpus embeddings loaded: {len(_corpus_texts)} phrases."
        )
        return _corpus_embeddings

    except Exception as e:
        logger.warning(f"[NORMALIZER] Corpus embedding load failed: {e} — normalization disabled.")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def normalize(query: str) -> tuple[str, bool, float]:
    """
    Normalize a potentially typo-laden or abbreviated embedded query.

    Returns:
        (normalized_query, was_normalized, confidence_score)

        normalized_query: The query with canonical form appended if a match
                          was found above threshold; otherwise the raw query.
        was_normalized:   True if a normalization was applied.
        confidence_score: Cosine similarity of the best match (0.0 if bypassed).

    Contract:
        - NEVER raises an exception to caller.
        - NEVER replaces the raw query — only appends canonical hint.
        - NEVER modifies hardware register names or numeric parameters.
        - Falls back to (raw_query, False, 0.0) on any failure.
    """
    if not query or not query.strip():
        return query, False, 0.0

    # Guard: if query contains register names, skip normalization
    # (register-level queries are already precise enough)
    if _REGISTER_PATTERN.search(query):
        return query, False, 0.0

    # Skip very long queries (likely already fully specified)
    if len(query) > 200:
        return query, False, 0.0

    try:
        import numpy as np
        from app.services.embeddings import get_model, model_ready

        if not model_ready():
            return query, False, 0.0

        corpus_embs = _load_corpus_embeddings()
        if corpus_embs is None:
            return query, False, 0.0

        m = get_model()
        q_emb = m.encode([query], convert_to_tensor=False)

        # Cosine similarity
        q_norm = q_emb / (np.linalg.norm(q_emb, axis=1, keepdims=True) + 1e-9)
        c_norm = corpus_embs / (np.linalg.norm(corpus_embs, axis=1, keepdims=True) + 1e-9)
        similarities = (q_norm @ c_norm.T).flatten()

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= NORMALIZE_THRESHOLD:
            canonical = NORMALIZATION_CORPUS[best_idx][1]
            # Append canonical form only if meaningfully different from raw query
            raw_lower = query.strip().lower()
            can_lower = canonical.strip().lower()
            if raw_lower == can_lower or can_lower in raw_lower:
                # Already contains canonical form — no append needed
                return query, False, best_score

            normalized = f"{query.strip()} [{canonical}]"
            logger.info(
                f"[NORMALIZER] '{query}' → '{canonical}' "
                f"(score={best_score:.3f})"
            )
            return normalized, True, best_score

        return query, False, best_score

    except Exception as e:
        logger.warning(f"[NORMALIZER] Normalization failed: {e} — using raw query.")
        return query, False, 0.0


def is_modification_query(query: str) -> bool:
    """
    Quick check: does this query look like a modification intent
    rather than a fresh architecture generation request?

    Uses keyword matching (deterministic, zero latency).
    Called by the /chat pipeline before running full normalization.
    """
    q = query.lower().strip()
    modification_signals = [
        # Removals
        "remove", "delete", "rm", "drop", "clear", "free", "release",
        # Queue / Stack / Priority / Mutex
        "make", "bigger", "larger", "deeper", "increase", "decrease", "add", "incr", "lower",
        "reduce", "optimize", "change", "modify", "update", "priority", "prio", "stack", "stk",
        # Features / Protocols
        "overflow", "watermark", "replace", "convert", "swap", "dma", "watchdog", "wdt", "wdg",
        "mutex", "latency", "jitter", "rms"
    ]
    return any(re.search(rf"\b{re.escape(sig)}\b", q) for sig in modification_signals)
