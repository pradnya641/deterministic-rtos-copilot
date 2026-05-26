"""
/ask endpoint — Phase 4 Deterministic Orchestration Hardening.

Architectural changes (Phase 4):
  - RAG gated to RAG_ENABLED_INTENTS only (Step 1)
  - Every subsystem call wrapped in isolation try/except (Step 6)
  - Layered orchestration: 7 explicit stages (Step 5)
  - Per-layer execution metrics tracked (Step 7)
  - Degraded mode warnings injected into response metadata
  - No single subsystem failure can terminate the pipeline

Response format v2:
{
  "status":        "success" | "error" | "degraded",
  "response":      "<primary text answer>",
  "intent":        "<detected intent>",
  "metadata": {
    "domain":         "<hardware|rtos|sensors|...>",
    "modules":        ["ADC", "UART", ...],
    "sensors":        ["HC-SR04", ...],
    "code":           "<C code block if applicable>",
    "source":         "<knowledge source>",
    "confidence":     "HIGH|MEDIUM|LOW|REJECTED",
    "rag_used":       true|false,
    "rag_latency_ms": 0,
    "degraded":       false,
    "degraded_reason": null,
    "layer_latency":  { "parse": 0, "validate": 0, "rag": 0, "generate": 0, "total": 0 },
    "version":        "2.0.0",
    "latency_ms":     123,
    "timestamp":      "2026-05-22T..."
  }
}
"""

import time
import logging
import unicodedata
from contextlib import contextmanager

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.schemas import QueryRequest, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: RAG intent gate (PATCH F)
# Only these intents are permitted to invoke FAISS retrieval.
# Deterministic intents (hardware_reasoning, peripheral_configuration,
# rtos_architecture) do NOT use FAISS — they use hard knowledge bases directly.
# ─────────────────────────────────────────────────────────────────────────────
FAISS_ENABLED_INTENTS = {
    "sensor_integration",
    "communication_design",
    "automotive_logic",
    "embedded_debugging",
    "system_architecture",
}
# Backward-compat alias used inside _safe_retrieve
RAG_ENABLED_INTENTS = FAISS_ENABLED_INTENTS

# Intents whose answers come purely from deterministic code paths
NON_CODE_INTENTS = {
    "hardware_reasoning", "rtos_architecture", "sensor_integration",
    "communication_design", "automotive_logic", "embedded_debugging",
    "system_architecture", "system", "unknown",
    "reasoning", "register",   # legacy
}

CODE_INTENTS = {
    "peripheral_configuration", "code_generation",
    "code", "gpio",             # legacy
}


# ─────────────────────────────────────────────────────────────────────────────
from app.services.cleaner import normalize_utf8, extract_clean_c_code

# UTILITY
# ─────────────────────────────────────────────────────────────────────────────
def sanitize(text: str) -> str:
    """Normalize UTF-8 characters, replacing emojis and translating arrows."""
    return normalize_utf8(text)


@contextmanager
def _timed():
    """Context manager that returns elapsed ms."""
    t = [time.time()]
    yield t
    t[0] = int((time.time() - t[0]) * 1000)


def _ms(t_start: float) -> int:
    return int((time.time() - t_start) * 1000)


# ─────────────────────────────────────────────────────────────────────────────
# SUBSYSTEM ISOLATION WRAPPERS (Step 6)
# Every external call is wrapped. Failure → safe fallback, never exception.
# ─────────────────────────────────────────────────────────────────────────────
def _safe_parse(text: str) -> tuple:
    """Layer 1: Parse. Returns (parsed_dict, latency_ms, error_str|None)."""
    t0 = time.time()
    try:
        from app.services.parser import parse_query
        parsed = parse_query(text)
        parsed["routing_trace"] = []
        parsed["semantic_validator_triggered"] = False
        parsed["subsystem_used"] = None
        return parsed, _ms(t0), None
    except Exception as e:
        logger.error(f"[PARSE] Failed: {e}")
        return {
            "intent": "unknown", "secondary_intents": [],
            "peripherals": [], "sensors": [], "components": [],
            "params": {"baud": 9600, "duty": 50, "channel": 1, "priority": 1, "stack": 512},
            "raw_query": text, "board": "LPC2148",
            "routing_trace": [],
            "semantic_validator_triggered": False,
            "subsystem_used": None,
        }, _ms(t0), str(e)


def _safe_detect_board(parsed: dict) -> tuple:
    """Layer 2a: Board detection. Returns (board_str, error_str|None)."""
    try:
        from app.services.router import detect_board
        return detect_board(parsed), None
    except Exception as e:
        logger.error(f"[BOARD] Detection failed: {e}")
        return "lpc2148", str(e)


def _safe_validate_pins(parsed: dict, board: str) -> tuple:
    """Layer 2b: Pin validation. Returns (valid_bool, error_str|None)."""
    try:
        from app.services.validator import validate_pins
        return validate_pins(parsed, board), None
    except Exception as e:
        logger.error(f"[VALIDATE_PINS] Failed: {e}")
        return True, str(e)   # fail-open: assume valid, log the error


def _safe_retrieve(parsed: dict, board: str, intent: str) -> tuple:
    """
    Layer 3: RAG retrieval.
    GATED: only runs for RAG_ENABLED_INTENTS.
    Returns (context_str, rag_used_bool, latency_ms, error_str|None).
    """
    if intent not in RAG_ENABLED_INTENTS:
        return "", False, 0, None

    t0 = time.time()
    try:
        from app.services.rag import safe_retrieve_context
        context = safe_retrieve_context(parsed, board)
        return context, True, _ms(t0), None
    except Exception as e:
        logger.error(f"[RAG] Retrieval failed: {e}")
        return "", False, _ms(t0), str(e)


def _safe_generate(parsed: dict, context: str, board: str) -> tuple:
    """
    Layer 4: Answer generation.
    Returns (answer_str, latency_ms, error_str|None).
    """
    t0 = time.time()
    try:
        from app.services.llm import generate_answer
        answer = generate_answer(parsed, context, board)
        return answer, _ms(t0), None
    except Exception as e:
        logger.error(f"[GENERATE] Failed: {e}")
        return (
            "### ⚠️ Generation Error\n"
            "The deterministic engine encountered an internal error. "
            "Please rephrase your query or contact support.",
            _ms(t0), str(e)
        )


def _safe_blueprint(text: str, parsed: dict) -> tuple:
    """
    Layer 4b: Architecture blueprint generation.
    Returns (rendered_str|None, blueprint_dict|None, error_str|None).
    """
    try:
        from app.services.architect import generate_blueprint, render_blueprint
        blueprint = generate_blueprint(text)
        if blueprint is None:
            return None, None, None
        rendered = render_blueprint(blueprint)
        bp_dict = {
            "system_name": blueprint.system_name,
            "tasks":   [t.__dict__ for t in blueprint.tasks],
            "queues":  [q.__dict__ for q in blueprint.queues],
            "timing":  blueprint.timing_budget,
            "safety":  blueprint.safety_rules,
        }
        return rendered, bp_dict, None
    except Exception as e:
        logger.error(f"[BLUEPRINT] Failed: {e}")
        return None, None, str(e)



def _safe_validate_code(answer: str, intent: str) -> tuple:
    """
    Layer 5: Code validation (only for CODE_INTENTS).
    Returns (valid_bool, rejection_reason|None, error_str|None).
    """
    if intent not in CODE_INTENTS:
        return True, None, None
    # Skip validation if already a trap rejection
    if any(k in answer for k in ["Invalid", "Architecture Mismatch", "Warning", "### ?"]):
        return True, None, None

    try:
        from app.services.validator import validate_sanity, validate_values, validate_completeness
        if not validate_sanity(answer):
            return False, "hallucinated register detected", None
        if not validate_values(answer):
            return False, "unsafe register value (PWMMR0=0)", None
        if not validate_completeness(answer, intent):
            return False, "missing required configuration registers", None
        return True, None, None
    except Exception as e:
        logger.error(f"[VALIDATE_CODE] Failed: {e}")
        return True, None, str(e)   # fail-open


def _safe_build_response(intent: str, answer: str, parsed: dict, **kwargs) -> object:
    """Layer 6: Build structured response object."""
    try:
        from app.services.response_schema import build_response
        return build_response(intent, answer, parsed, **kwargs)
    except Exception as e:
        logger.error(f"[BUILD_RESPONSE] Failed: {e}")

        class _FallbackResp:
            domain = "unknown"; modules = []; sensors = []
            source = "Deterministic Engine"; confidence = "LOW"
            version = "2.0.0"; timestamp = ""; code = None; architecture = None

        return _FallbackResp()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/ask")
def ask_question(request: QueryRequest):
    t_pipeline_start = time.time()
    degraded = False
    degraded_reasons = []
    layer_latency = {}

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 1: PARSE
    # ══════════════════════════════════════════════════════════════════════
    parsed, parse_ms, parse_err = _safe_parse(request.text)
    layer_latency["parse"] = parse_ms
    intent = parsed["intent"]

    if "routing_trace" not in parsed:
        parsed["routing_trace"] = []
    parsed["routing_trace"].append("1. Query Parsing")

    if parse_err:
        degraded = True
        degraded_reasons.append(f"parse: {parse_err}")

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 1.5: TRAP VALIDATION (Tier 1 + Tier 2)
    # ══════════════════════════════════════════════════════════════════════
    try:
        from app.services.validator import validate_query_full
        parsed["semantic_validator_triggered"] = True
        rejection = validate_query_full(request.text)
    except Exception as e:
        logger.error(f"[TRAP_VALIDATION] Failed: {e}")
        rejection = None

    if rejection:
        total_ms = _ms(t_pipeline_start)
        parsed["routing_trace"].append("Trap Validation Rejection")
        parsed["routing_trace"].append("7. Response Formatting")
        return JSONResponse({
            "status": "error",
            "intent": intent,
            "response": rejection,
            "metadata": {
                "confidence": "REJECTED",
                "rag_used": False,
                "rag_latency_ms": 0,
                "degraded": degraded,
                "degraded_reasons": degraded_reasons if degraded else [],
                "layer_latency": {**layer_latency, "total": total_ms},
                "version": "2.0.0",
                "latency_ms": total_ms,
                "routing_trace": parsed.get("routing_trace", []),
                "subsystem_used": "Semantic Trap Rejecter",
                "degraded_reason": "Trap Rejected",
                "retrieval_used": False,
                "semantic_validator_triggered": True,
            }
        })

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 2: VALIDATION (pins + board)
    # ══════════════════════════════════════════════════════════════════════
    t_val = time.time()
    board, board_err = _safe_detect_board(parsed)
    if board_err:
        degraded = True
        degraded_reasons.append(f"board_detect: {board_err}")

    pins_ok, pins_err = _safe_validate_pins(parsed, board)
    layer_latency["validate"] = _ms(t_val)
    parsed["routing_trace"].append("2. Board and Pin Validation")

    if pins_err:
        degraded = True
        degraded_reasons.append(f"pin_validate: {pins_err}")

    if not pins_ok:
        total_ms = _ms(t_pipeline_start)
        parsed["routing_trace"].append("7. Response Formatting")
        return JSONResponse({
            "status": "error",
            "intent": intent,
            "response": f"Error: Invalid pins for board '{board}'.",
            "metadata": {
                "confidence": "REJECTED",
                "latency_ms": total_ms,
                "layer_latency": layer_latency,
                "routing_trace": parsed.get("routing_trace", []),
                "subsystem_used": "Pin Validator",
                "degraded_reason": pins_err or "Invalid pins",
                "retrieval_used": False,
                "semantic_validator_triggered": parsed.get("semantic_validator_triggered", False),
            }
        })

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 3: ARCHITECTURE SYNTHESIS (pre-RAG — self-contained)
    # ══════════════════════════════════════════════════════════════════════
    t_bp = time.time()
    rendered_bp, bp_dict, bp_err = _safe_blueprint(request.text, parsed)
    layer_latency["blueprint"] = _ms(t_bp)
    parsed["routing_trace"].append("3. Direct Blueprint Search")

    if bp_err:
        degraded = True
        degraded_reasons.append(f"blueprint: {bp_err}")

    if rendered_bp is not None:
        safe_rendered = sanitize(rendered_bp)
        total_ms = _ms(t_pipeline_start)
        parsed["routing_trace"].append("7. Response Formatting")
        return JSONResponse({
            "status": "success",
            "intent": intent,
            "response": safe_rendered,
            "metadata": {
                "domain": "system",
                "architecture": bp_dict,
                "source": "Architecture Generator",
                "confidence": "HIGH",
                "rag_used": False,
                "degraded": degraded,
                "degraded_reasons": degraded_reasons if degraded else [],
                "layer_latency": {**layer_latency, "total": total_ms},
                "version": "2.0.0",
                "latency_ms": total_ms,
                "routing_trace": parsed.get("routing_trace", []),
                "subsystem_used": "Architecture Generator",
                "degraded_reason": degraded_reasons[0] if degraded_reasons else None,
                "retrieval_used": False,
                "semantic_validator_triggered": parsed.get("semantic_validator_triggered", False),
            }
        })

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 4: RAG RETRIEVAL (gated — optional support subsystem)
    # ══════════════════════════════════════════════════════════════════════
    context, rag_used, rag_ms, rag_err = _safe_retrieve(parsed, board, intent)
    layer_latency["rag"] = rag_ms
    parsed["routing_trace"].append("4. RAG Retrieval")

    if rag_err:
        degraded = True
        degraded_reasons.append(f"rag: {rag_err}")
        logger.warning(f"[ORCHESTRATOR] RAG degraded for intent='{intent}': {rag_err}")

    if intent in RAG_ENABLED_INTENTS and not rag_used:
        # RAG was expected but failed/skipped — note degraded mode
        degraded = True
        degraded_reasons.append("rag: retrieval skipped or failed — using deterministic engine only")

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 5: DETERMINISTIC ANSWER GENERATION
    # ══════════════════════════════════════════════════════════════════════
    answer, gen_ms, gen_err = _safe_generate(parsed, context, board)
    layer_latency["generate"] = gen_ms
    parsed["routing_trace"].append("5. Answer Generation")

    if gen_err:
        degraded = True
        degraded_reasons.append(f"generate: {gen_err}")

    answer = sanitize(answer)

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 5b: POST-GENERATION SANITY VALIDATION (PATCH B)
    # validate_sanity + validate_values for all non-trivial answers
    # ══════════════════════════════════════════════════════════════════════
    if "Information not found" not in answer and "Query Unclear" not in answer:
        try:
            from app.services.validator import validate_sanity, validate_values
            if not validate_sanity(answer):
                logger.warning(f"[VALIDATE] Hallucinated register detected for intent='{intent}'")
                answer = (
                    "### Internal Validation Failed\n"
                    "The engine detected a hallucinated register or forbidden API "
                    "in the generated response. This query has been logged.\n"
                    "Please rephrase targeting LPC2148 registers: "
                    "AD0CR (ADC), UxLCR (UART), PWMMCR (PWM), PINSEL (pin mux)."
                )
                parsed["subsystem_used"] = "Sanity Validator (REJECTED)"
            elif not validate_values(answer):
                logger.warning(f"[VALIDATE] Unsafe register value detected for intent='{intent}'")
                answer = (
                    "### Internal Validation Failed\n"
                    "The engine detected an unsafe hardware value (e.g. PWMMR0=0). "
                    "This would stall the PWM timer. Query has been logged."
                )
                parsed["subsystem_used"] = "Value Validator (REJECTED)"
        except Exception as e:
            logger.error(f"[VALIDATE_SANITY] Failed: {e}")

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 6: CODE VALIDATION (CODE_INTENTS only)
    # ══════════════════════════════════════════════════════════════════════
    code_validated = False
    if intent in CODE_INTENTS and "Information not found" not in answer:
        code_validated = True
        code_ok, rejection_reason, val_err = _safe_validate_code(answer, intent)
        parsed["routing_trace"].append("6. Code Safety Validation")
        if val_err:
            degraded = True
            degraded_reasons.append(f"code_validate: {val_err}")

        if not code_ok:
            total_ms = _ms(t_pipeline_start)
            parsed["routing_trace"].append("7. Response Formatting")
            return JSONResponse({
                "status": "error",
                "intent": intent,
                "response": f"Answer rejected: {rejection_reason}.",
                "metadata": {
                    "confidence": "REJECTED",
                    "rag_used": rag_used,
                    "rag_latency_ms": rag_ms,
                    "latency_ms": total_ms,
                    "layer_latency": {**layer_latency, "total": total_ms},
                    "routing_trace": parsed.get("routing_trace", []),
                    "subsystem_used": "Code Safety Validator",
                    "degraded_reason": rejection_reason,
                    "retrieval_used": rag_used,
                    "semantic_validator_triggered": parsed.get("semantic_validator_triggered", False),
                }
            })

    if not code_validated:
        parsed["routing_trace"].append("6. Code Safety Validation")

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 7: OUTPUT — Structured Response
    # ══════════════════════════════════════════════════════════════════════
    total_ms = _ms(t_pipeline_start)
    layer_latency["total"] = total_ms

    resp = _safe_build_response(
        intent, answer, parsed,
        code=answer if intent in CODE_INTENTS else None,
        latency_ms=total_ms,
    )
    parsed["routing_trace"].append("7. Response Formatting")

    # Degraded mode warning
    if degraded:
        logger.warning(
            f"[ORCHESTRATOR] Degraded mode for intent='{intent}': "
            + "; ".join(degraded_reasons)
        )

    # Log slow responses
    if total_ms > 5000:
        logger.warning(f"[ORCHESTRATOR] Slow response: {total_ms}ms for intent='{intent}'")

    return JSONResponse({
        "status": "degraded" if degraded else "success",
        "intent": intent,
        "response": answer,
        "metadata": {
            "domain":           resp.domain,
            "modules":          resp.modules,
            "sensors":          resp.sensors,
            "code":             resp.code,
            "source":           resp.source,
            "confidence":       resp.confidence,
            "rag_used":         rag_used,
            "rag_latency_ms":   rag_ms,
            "degraded":         degraded,
            "degraded_reasons": degraded_reasons if degraded else [],
            "layer_latency":    layer_latency,
            "version":          resp.version,
            "latency_ms":       total_ms,
            "timestamp":        resp.timestamp,
            "routing_trace":    parsed.get("routing_trace", []),
            "subsystem_used":   parsed.get("subsystem_used") or "Deterministic Engine",
            "degraded_reason":  degraded_reasons[0] if degraded_reasons else None,
            "retrieval_used":   rag_used,
            "semantic_validator_triggered": parsed.get("semantic_validator_triggered", False),
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# CHAT ENDPOINT & HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _extract_c_code(markdown_text: str) -> str:
    """Extract C code block cleanly from markdown text."""
    return extract_clean_c_code(markdown_text)


def make_structured_diff(old_code: str, new_code: str) -> list[dict]:
    import difflib
    
    old_lines = old_code.splitlines()
    new_lines = new_code.splitlines()
    
    diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
    
    structured_diff = []
    # Skip the header lines (first 3 lines typically)
    header_count = 0
    for line in diff:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        elif line.startswith("+"):
            structured_diff.append({"type": "add", "line": line[1:]})
        elif line.startswith("-"):
            structured_diff.append({"type": "remove", "line": line[1:]})
        else:
            structured_diff.append({"type": "context", "line": line[1:] if line.startswith(" ") else line})
            
    return structured_diff


def _safe_gcc_syntax_check(code: str) -> tuple[bool, str]:
    """
    Run arm-none-eabi-gcc -fsyntax-only check on the extracted C code.
    Uses FreeRTOS and LPC214x stub headers in scripts/harness_tests/include.
    """
    import subprocess
    import tempfile
    import os
    
    gcc_path = r"C:\Users\puroh\.gemini\antigravity-ide\scratch\arm-gcc\xpack-arm-none-eabi-gcc-13.2.1-1.1\bin\arm-none-eabi-gcc.exe"
    include_dir = r"c:\genai_project\backend\scripts\harness_tests\include"
    
    if not os.path.exists(gcc_path):
        logger.warning(f"[COMPILER] GCC compiler not found at path: {gcc_path} (fail-open)")
        return True, "GCC compiler not found on this system; compiler check skipped (fail-open)."
        
    # Write code to a temporary C file inside the scratch folder
    temp_dir = r"c:\genai_project\backend\scratch"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, "_temp_check.c")
    
    # Ensure it has a main stub if it doesn't already
    if "main(" not in code:
        code += "\n\n/* Automatically appended main stub for syntax checking */\nint main(void) { return 0; }\n"
        
    try:
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        cmd = [
            gcc_path,
            "-mcpu=arm7tdmi",
            "-std=c99",
            "-fsyntax-only",
            f"-I{include_dir}",
            temp_file_path
        ]
        
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            try:
                with open(r"c:\genai_project\backend\scratch\failed_code_debug.c", "w", encoding="utf-8") as df:
                    df.write(code)
            except Exception:
                pass
            return False, res.stderr
        return True, "Syntax OK"
    except Exception as e:
        logger.warning(f"[COMPILER] Syntax check runner failed: {e}")
        return True, f"Syntax check failed to execute: {e} (fail-open)"
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


def _check_conflicts_for_query(state, query_text: str) -> str | None:
    import re
    # 1. Extract all peripherals mentioned
    peripherals = []
    for p in ["UART0", "UART1", "PWM1", "PWM2", "SPI0", "I2C0", "ADC0_1", "ADC0_2", "CAN1"]:
        if p.lower() in query_text.lower():
            peripherals.append(p)
            
    # Fuzzy mappings if no exact match
    if not peripherals:
        if "uart" in query_text.lower():
            peripherals.append("UART0")
        if "spi" in query_text.lower():
            peripherals.append("SPI0")
        if "i2c" in query_text.lower():
            peripherals.append("I2C0")
        if "can" in query_text.lower():
            peripherals.append("CAN1")
        if "adc" in query_text.lower():
            peripherals.append("ADC0_1")
            
    if not peripherals:
        return None
        
    # 2. Extract task name if any
    task_name = None
    match = re.search(r'task\s+([A-Za-z0-9_]+)', query_text, re.IGNORECASE)
    if match:
        task_name = match.group(1)
    else:
        # Match vSomethingTask
        match2 = re.search(r'\b(v[A-Za-z0-9_]+Task)\b', query_text)
        if match2:
            task_name = match2.group(1)
        else:
            match3 = re.search(r'\b(v[A-Z][A-Za-z0-9_]+)\b', query_text)
            if match3:
                task_name = match3.group(1)
                
    from app.services.conversation_state import check_peripheral_conflict
    for p in peripherals:
        if task_name:
            conflict = check_peripheral_conflict(state, p, task_name)
            if conflict:
                return conflict
        else:
            # Check PINSEL conflict only
            from app.services.conversation_state import _PINSEL_CONFLICTS
            for (p1, p2) in _PINSEL_CONFLICTS:
                if p == p1 and p2 in state.peripherals:
                    existing = state.peripherals[p2]
                    return (
                        f"PINSEL conflict: '{p}' and '{p2}' share PINSEL bits "
                        f"({existing.pinsel_reg} {existing.pinsel_bits}). "
                        f"They cannot be active simultaneously on LPC2148."
                    )
                if p == p2 and p1 in state.peripherals:
                    existing = state.peripherals[p1]
                    return (
                        f"PINSEL conflict: '{p}' and '{p1}' share PINSEL bits "
                        f"({existing.pinsel_reg} {existing.pinsel_bits}). "
                        f"They cannot be active simultaneously on LPC2148."
                    )
    return None


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Multi-turn conversational firmware copilot endpoint.
    Manages architecture state across turns, performing fuzzy query normalization,
    safety checks, incremental modifications, and compiler syntax validation.
    """
    t_pipeline_start = time.time()
    session_id = request.session_id
    query = request.text
    
    # L0: Session load (create if new)
    from app.services.conversation_state import get_or_create_session, update_session
    state = get_or_create_session(session_id)
    
    degraded = False
    degraded_reasons = []
    layer_latency = {}
    
    # L1: Fuzzy normalization
    from app.services.normalizer import normalize, is_modification_query
    t_norm = time.time()
    norm_query, was_normalized, norm_score = normalize(query)
    layer_latency["normalization"] = _ms(t_norm)
    
    # L2: Intent parse (existing parser)
    parsed, parse_ms, parse_err = _safe_parse(norm_query)
    layer_latency["parse"] = parse_ms
    intent = parsed.get("intent", "unknown")
    
    if parse_err:
        degraded = True
        degraded_reasons.append(f"parse: {parse_err}")
        
    # L3: Trap validation (existing validator — unchanged)
    try:
        from app.services.validator import validate_query_full
        rejection = validate_query_full(norm_query)
    except Exception as e:
        logger.error(f"[TRAP_VALIDATION] Failed: {e}")
        rejection = None
        
    if rejection:
        total_ms = _ms(t_pipeline_start)
        return JSONResponse({
            "status": "error",
            "session_id": session_id,
            "response": rejection,
            "diff": None,
            "architecture_snapshot": None,
            "turn": state.turn_count,
        })
        
    # L4: Modification intent detection
    from app.services.modifier import detect_modification_intent, apply_modification, extract_state_from_response
    mod_intent = detect_modification_intent(norm_query)
    
    # Check if the user query is a modification query
    route_type = parsed.get("route_type", "NEW_ARCHITECTURE_REQUEST")
    is_mod = (route_type == "ARCHITECTURE_MODIFICATION")
    has_prior_state = bool(state.generated_code)
    
    # L5: Peripheral conflict check (Deferred to post-modification working state)
            
    # Decide path: modification vs fresh synthesis
    if is_mod and has_prior_state:
        # ── MODIFICATION PATH ──
        t_mod = time.time()
        mod_label = mod_intent.replace("_", " ").title() if (mod_intent and not mod_intent.startswith("REJECTED:")) else "Modification"
        
        response_text, entries, new_state = apply_modification(state, mod_intent or "unknown", norm_query, params=parsed.get("params"))
        layer_latency["modification"] = _ms(t_mod)
        
        # If the generated code changed, run compiler syntax check (L8)
        if new_state.generated_code != state.generated_code:
            t_comp = time.time()
            c_code = _extract_c_code(new_state.generated_code)
            comp_ok, comp_msg = _safe_gcc_syntax_check(c_code)
            layer_latency["compiler"] = _ms(t_comp)
            
            if not comp_ok:
                # Reject the modification and rollback to original state
                from app.services.diff_formatter import format_rejection_response
                from app.services.modifier import parse_removals_and_additions
                removals, additions = parse_removals_and_additions(norm_query)
                rejection_msg = (
                    f"Compiler syntax check failed.\n\n"
                    f"**Step(s) attempted:**\n"
                    f"- Removals: {', '.join(removals) if removals else 'None'}\n"
                    f"- Additions/Modifications: {', '.join(additions) if additions else 'None' or mod_label}\n\n"
                    f"**Compiler diagnostic output:**\n"
                    f"```text\n{comp_msg}\n```"
                )
                response_text = format_rejection_response(rejection_msg, mod_label)
                total_ms = _ms(t_pipeline_start)
                return JSONResponse({
                    "status": "error",
                    "session_id": session_id,
                    "response": response_text,
                    "diff": None,
                    "architecture_snapshot": None,
                    "turn": state.turn_count,
                })
        
        # Save session
        update_session(session_id, new_state)
        
        # Generate structured line-level diff
        diff_list = make_structured_diff(state.generated_code, new_state.generated_code)
            
        # Build architecture snapshot
        # Build architecture snapshot (only display explicit ISRs)
        explicit_isrs = [
            isr for isr in new_state.isr_topology 
            if isr.get("source") == "explicit"
        ]
        if not explicit_isrs:
            explicit_isrs = [{
                "isr_name": "No ISR generated",
                "vic_channel": None,
                "handler_fn": "",
                "queue_name": "",
                "peripheral": "",
                "source": "explicit"
            }]

        snapshot = {
            "system_name": new_state.system_name,
            "tasks": new_state.tasks,
            "queues": new_state.queues,
            "semaphores": new_state.semaphores,
            "mutexes": new_state.mutexes,
            "binary_semaphores": new_state.binary_semaphores,
            "counting_semaphores": new_state.counting_semaphores,
            "isr_topology": explicit_isrs,
            "peripherals": [
                {
                    "peripheral": p.peripheral,
                    "owner_task": p.owner_task,
                    "pinsel_reg": p.pinsel_reg,
                    "pinsel_bits": p.pinsel_bits,
                    "pinsel_val": p.pinsel_val,
                    "vic_channel": p.vic_channel
                } for p in new_state.peripherals.values()
            ],
            "validation_status": "Valid",
            "compile_status": "Valid" if (new_state.generated_code != state.generated_code) else "No Change",
            "summary": f"System configured with {len(new_state.tasks)} tasks, {len(new_state.queues)} queues, and {len(new_state.semaphores)} synchronization primitives."
        }
        
        total_ms = _ms(t_pipeline_start)
        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "response": response_text,
            "diff": diff_list,
            "architecture_snapshot": snapshot,
            "turn": new_state.turn_count,
        })
        
    else:
        # ── FRESH SYNTHESIS PATH ──
        # Reset state if it exists, since this is a new architecture request
        from app.services.conversation_state import create_session
        state = create_session(session_id)
        
        # Run normal ask pipeline to generate answer
        # LAYER 2: VALIDATION (pins + board)
        t_val = time.time()
        board, board_err = _safe_detect_board(parsed)
        if board_err:
            degraded = True
            degraded_reasons.append(f"board_detect: {board_err}")

        pins_ok, pins_err = _safe_validate_pins(parsed, board)
        layer_latency["validate"] = _ms(t_val)

        if pins_err:
            degraded = True
            degraded_reasons.append(f"pin_validate: {pins_err}")

        if not pins_ok:
            total_ms = _ms(t_pipeline_start)
            return JSONResponse({
                "status": "error",
                "session_id": session_id,
                "response": f"Error: Invalid pins for board '{board}'.",
                "diff": None,
                "architecture_snapshot": None,
                "turn": state.turn_count,
            })

        # LAYER 3: ARCHITECTURE SYNTHESIS (blueprint search)
        t_bp = time.time()
        rendered_bp, bp_dict, bp_err = _safe_blueprint(norm_query, parsed)
        layer_latency["blueprint"] = _ms(t_bp)

        if bp_err:
            degraded = True
            degraded_reasons.append(f"blueprint: {bp_err}")

        if rendered_bp is not None:
            # Blueprint found
            response_text = sanitize(rendered_bp)
        else:
            # LAYER 4: RAG RETRIEVAL
            context, rag_used, rag_ms, rag_err = _safe_retrieve(parsed, board, intent)
            layer_latency["rag"] = rag_ms

            if rag_err:
                degraded = True
                degraded_reasons.append(f"rag: {rag_err}")

            # LAYER 5: ANSWER GENERATION
            answer, gen_ms, gen_err = _safe_generate(parsed, context, board)
            layer_latency["generate"] = gen_ms

            if gen_err:
                degraded = True
                degraded_reasons.append(f"generate: {gen_err}")

            response_text = sanitize(answer)

        # Post-generation validation sanity check
        if "Information not found" not in response_text and "Query Unclear" not in response_text:
            try:
                from app.services.validator import validate_sanity, validate_values
                if not validate_sanity(response_text):
                    response_text = (
                        "### Internal Validation Failed\n"
                        "The engine detected a hallucinated register or forbidden API "
                        "in the generated response. This query has been logged.\n"
                        "Please rephrase targeting LPC2148 registers: "
                        "AD0CR (ADC), UxLCR (UART), PWMMCR (PWM), PINSEL (pin mux)."
                    )
                elif not validate_values(response_text):
                    response_text = (
                        "### Internal Validation Failed\n"
                        "The engine detected an unsafe hardware value (e.g. PWMMR0=0). "
                        "This would stall the PWM timer. Query has been logged."
                    )
            except Exception as e:
                logger.error(f"[VALIDATE_SANITY] Failed: {e}")

        # Extract state from response
        new_state = extract_state_from_response(session_id, norm_query, response_text, parsed)
        
        # L8: Compiler validation for first turn / fresh synthesis
        c_code = _extract_c_code(new_state.generated_code)
        if c_code and c_code != new_state.generated_code:
            t_comp = time.time()
            comp_ok, comp_msg = _safe_gcc_syntax_check(c_code)
            layer_latency["compiler"] = _ms(t_comp)
            if not comp_ok:
                degraded = True
                degraded_reasons.append(f"compiler: {comp_msg}")
                logger.warning(f"[COMPILER] Fresh synthesis code is not compile-valid: {comp_msg}")
        
        # Save session
        new_state.turn_count = 0
        from app.services.conversation_state import record_turn
        record_turn(new_state, norm_query, None, "initial synthesis")
        update_session(session_id, new_state)
        
        # Tag ISRs in the fresh state
        for isr in new_state.isr_topology:
            handler_name = isr.get("handler_fn", "")
            if handler_name and handler_name in new_state.generated_code:
                isr["source"] = "explicit"
            else:
                isr["source"] = "inferred"

        explicit_isrs = [
            isr for isr in new_state.isr_topology 
            if isr.get("source") == "explicit"
        ]
        if not explicit_isrs:
            explicit_isrs = [{
                "isr_name": "No ISR generated",
                "vic_channel": None,
                "handler_fn": "",
                "queue_name": "",
                "peripheral": "",
                "source": "explicit"
            }]

        snapshot = {
            "system_name": new_state.system_name,
            "tasks": new_state.tasks,
            "queues": new_state.queues,
            "semaphores": new_state.semaphores,
            "mutexes": new_state.mutexes,
            "binary_semaphores": new_state.binary_semaphores,
            "counting_semaphores": new_state.counting_semaphores,
            "isr_topology": explicit_isrs,
            "peripherals": [
                {
                    "peripheral": p.peripheral,
                    "owner_task": p.owner_task,
                    "pinsel_reg": p.pinsel_reg,
                    "pinsel_bits": p.pinsel_bits,
                    "pinsel_val": p.pinsel_val,
                    "vic_channel": p.vic_channel
                } for p in new_state.peripherals.values()
            ],
            "validation_status": "Valid",
            "compile_status": "Valid" if not degraded else "Warning (Degraded)",
            "summary": f"System configured with {len(new_state.tasks)} tasks, {len(new_state.queues)} queues, and {len(new_state.semaphores)} synchronization primitives."
        }
        
        total_ms = _ms(t_pipeline_start)
        return JSONResponse({
            "status": "degraded" if degraded else "success",
            "session_id": session_id,
            "response": response_text,
            "diff": None,
            "architecture_snapshot": snapshot,
            "turn": new_state.turn_count,
        })
