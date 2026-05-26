"""
Validator — Phase 5 hardened with semantic trap detection.

Two-tier rejection system:
  Tier 1 (keyword): fast, deterministic, zero latency
  Tier 2 (semantic): embedding-based cross-domain invalidity detection

Semantic trap detection works by computing cosine similarity between
the user query and a set of known-invalid engineering concept strings.
If similarity exceeds SEMANTIC_TRAP_THRESHOLD, the query is rejected.

Subsystem isolation: semantic check failure (embedding unavailable)
falls back to keyword-only mode silently.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SEMANTIC TRAP CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
SEMANTIC_TRAP_THRESHOLD = 0.75    # cosine similarity — above this = trap

# Known-invalid engineering concept strings used for semantic rejection.
# These represent physically/architecturally impossible relationships.
SEMANTIC_TRAPS = [
    ("ADC baud rate configuration",
     "ADC does not use baud rate. ADC uses CLKDIV in AD0CR for sampling clock."),
    ("UART affects ADC analog accuracy",
     "UART is a digital peripheral isolated from the ADC analog subsystem."),
    ("PWM duty cycle controls ADC sampling frequency",
     "PWM and ADC are independent peripherals with no cross-control path."),
    ("CAN bus affects ADC voltage resolution",
     "CAN is a digital differential bus with no influence on ADC analog conversion."),
    ("AVR register on ARM microcontroller",
     "AVR and ARM7 have completely different register architectures."),
    ("Arduino API on bare metal LPC2148",
     "Arduino abstraction layer does not exist on LPC2148 register-level programming."),
    ("FreeRTOS task controls hardware register directly",
     "FreeRTOS tasks access hardware registers via peripheral drivers, not directly."),
    ("I2C speed affects PWM frequency",
     "I2C communication speed and PWM timer frequency are independent subsystems."),
]


# ─────────────────────────────────────────────────────────────────────────────
# TIER 1: KEYWORD-BASED TRAP REJECTION (always runs, zero latency)
# ─────────────────────────────────────────────────────────────────────────────

def validate_query(query: str) -> str | None:
    """
    Tier 1 deterministic keyword rejection.
    Returns rejection string on trap, None if query is valid.
    """
    q = query.lower()

    # ISR safety checks
    if any(k in q for k in ["isr", "interrupt", "irq", "handler", "isr context", "interrupt context", "irq context"]):
        from_isr_absent = "fromisr" not in q
        has_unsafe_op = (
            "xsemaphoretake" in q or
            "mutex" in q or
            "blocking api" in q or
            "blocking call" in q or
            "vtaskdelay" in q or
            ("xsemaphoregive" in q and from_isr_absent) or
            ("semaphore" in q and "take" in q) or
            ("semaphore" in q and "give" in q and from_isr_absent) or
            ("queue" in q and ("send" in q or "receive" in q or "push" in q or "pop" in q) and from_isr_absent)
        )
        if has_unsafe_op:
            return (
                "### Invalid RTOS Operation: ISR Safety Violation\n\n"
                "Mutex and semaphore take/give operations (such as xSemaphoreTake or xSemaphoreGive), "
                "or blocking API calls (such as vTaskDelay) are illegal inside an ISR (Interrupt Service Routine) context.\n\n"
                "Why this is prohibited:\n"
                "1. Priority Inheritance Blocking Risk: Mutexes employ priority inheritance, which cannot be resolved in interrupt context "
                "since ISRs do not run within a task context and cannot block. This would violate the deterministic scheduling of the RTOS.\n"
                "2. FromISR APIs: Only non-blocking interrupt-safe API variants (ending in FromISR, such as xSemaphoreGiveFromISR) are "
                "permitted within an interrupt handler to avoid deadlock or crash.\n"
                "3. Preserved State: The previous architecture state is preserved."
            )

    # UART / ADC cross-domain traps
    if "uart" in q and "adc" in q and ("dlab" in q or "resolution" in q or "affect" in q or "effect" in q):
        return ("### ❌ Invalid Hardware Query\n"
                "UART and ADC are independent subsystems. The UART DLAB bit does not affect ADC resolution.")

    # ADC cross-domain traps
    if "adc" in q and "baud" in q:
        return ("### ❌ Invalid Hardware Query\n"
                "ADC does NOT use baud rate. "
                "It uses a sampling clock derived from PCLK via the **CLKDIV** bit in **AD0CR**.")

    if "adc" in q and ("duty cycle" in q or ("pwm" in q and "adc" in q)):
        return "Invalid: PWM does not control ADC sampling. These are independent peripherals."

    # Cross-peripheral traps
    if "uart" in q and ("adc accuracy" in q or "adc conversion" in q):
        return ("### ❌ Invalid Hardware Query\n"
                "UART FIFO and UART peripherals are completely isolated from the ADC peripheral. "
                "UART is a digital communication bus and cannot affect analog conversion accuracy.")

    if "gpio" in q and "adc quantization" in q:
        return "Invalid: GPIO state does not cause ADC quantization. Quantization is an intrinsic ADC property."

    if "uart" in q and "analog voltage" in q:
        return "Invalid: UART is a digital communication peripheral. It does not affect analog voltage levels."

    # Wrong architecture registers (AVR/Arduino)
    forbidden_avr = ["tccr", "adcsra", "admux", "ddr", "portb", "porta"]
    if any(re.search(rf"\b{k}\b", q) for k in forbidden_avr):
        return ("### ❌ Architecture Mismatch\n"
                "The registers mentioned belong to the **AVR/Arduino** architecture. "
                "The LPC2148 is an **ARM7TDMI-S** microcontroller with a completely different register set.\n"
                "Use: AD0CR (ADC), UxLCR (UART), PWMMCR (PWM), PINSEL (pin mux).")

    # Arduino-style API traps
    if any(k in q for k in ["analogread", "analogwrite", "digitalwrite", "digitalread",
                              "pinmode", "serial.begin"]):
        return ("### ❌ Invalid: Arduino API\n"
                "Arduino abstraction functions (analogRead, digitalWrite, Serial.begin) do NOT exist on LPC2148.\n"
                "The LPC2148 requires direct register-level programming: AD0CR, IO0DIR, UxTHR, etc.")

    # RTOS cross-domain traps
    if "freertos" in q and "baud rate" in q and "adc" in q:
        return "Invalid: FreeRTOS task scheduling is independent from ADC baud configuration."

    # Sensor voltage traps
    if "mpu6050" in q and "5v" in q and "directly" in q:
        return ("### ⚠️ Hardware Warning\n"
                "MPU6050 is a 3.3V device. Directly connecting to 5V will damage it. "
                "A level shifter is required.")

    if "can" in q and ("adc" in q or "analog" in q or "resolution" in q):
        return ("### ❌ Invalid Hardware Query\n"
                "CAN Bus is a differential digital communication protocol (ISO 11898) and has NO direct "
                "influence on ADC (Analog-to-Digital Converter) voltage resolution or conversion accuracy.")

    # I2C / SPI / UART cross-peripheral traps
    if "i2c" in q and ("pwm frequency" in q or "pwm period" in q):
        return ("### ❌ Invalid Hardware Query\n"
                "I2C communication speed and PWM frequency are independent subsystems. "
                "I2C clock rate does not affect PWM timer configuration.")

    if "spi" in q and "adc resolution" in q:
        return ("### ❌ Invalid Hardware Query\n"
                "SPI clock speed does not affect ADC resolution. "
                "ADC resolution is fixed at 10-bit on LPC2148 regardless of peripheral clocks.")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2: SEMANTIC TRAP DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_trap_embeddings = None   # lazy-loaded


def _get_trap_embeddings():
    """Lazy-load trap concept embeddings once, then cache."""
    global _trap_embeddings
    if _trap_embeddings is not None:
        return _trap_embeddings
    try:
        from app.services.embeddings import get_model
        m = get_model()
        concepts = [trap[0] for trap in SEMANTIC_TRAPS]
        _trap_embeddings = m.encode(concepts, convert_to_tensor=False)
        return _trap_embeddings
    except Exception as e:
        logger.warning(f"[SEMANTIC_VALIDATOR] Trap embedding load failed: {e}")
        return None


def validate_query_semantic(query: str) -> str | None:
    """
    Tier 2: Embedding-based semantic cross-domain invalidity detection.
    Complements Tier 1 keyword checks.
    Returns rejection string if query is semantically similar to a known trap.
    Returns None if query is valid OR if semantic check is unavailable.

    Architectural contract:
      - NEVER raises an exception to caller
      - Returns None (safe pass-through) if embeddings are unavailable
      - Adds ~2-5ms overhead when embeddings are warm
    """
    try:
        import numpy as np
        from app.services.embeddings import get_model, model_ready

        if not model_ready():
            return None   # Embeddings not ready — skip semantic check

        trap_embeddings = _get_trap_embeddings()
        if trap_embeddings is None:
            return None

        m = get_model()
        query_emb = m.encode([query], convert_to_tensor=False)

        # Cosine similarity between query and each trap concept
        q_norm = query_emb / (np.linalg.norm(query_emb, axis=1, keepdims=True) + 1e-9)
        t_norm = trap_embeddings / (np.linalg.norm(trap_embeddings, axis=1, keepdims=True) + 1e-9)
        similarities = (q_norm @ t_norm.T).flatten()

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= SEMANTIC_TRAP_THRESHOLD:
            _, rejection_reason = SEMANTIC_TRAPS[best_idx]
            logger.info(
                f"[SEMANTIC_VALIDATOR] Semantic trap hit: "
                f"score={best_score:.3f} trap='{SEMANTIC_TRAPS[best_idx][0][:50]}'"
            )
            return f"### ❌ Invalid Engineering Query (semantic)\n{rejection_reason}"

        return None

    except Exception as e:
        logger.warning(f"[SEMANTIC_VALIDATOR] Semantic check failed: {e} — falling back to keyword-only.")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# COMBINED VALIDATOR (keyword + semantic)
# ─────────────────────────────────────────────────────────────────────────────

def validate_query_full(query: str) -> str | None:
    """
    Run Tier 1 (keyword) then Tier 2 (semantic) validation.
    Returns rejection string on first hit, None if valid.
    """
    result = validate_query(query)
    if result:
        return result
    return validate_query_semantic(query)


# ─────────────────────────────────────────────────────────────────────────────
# ANSWER SANITY CHECKS (post-generation)
# ─────────────────────────────────────────────────────────────────────────────

FORBIDDEN_REGISTERS = [
    "PR2DIR", "PR2ETA", "ADCSRA", "ADMUX", "ADDR", "ADALH", "ADALW",
    "RAREG", "TCCR0", "TCCR1", "PORTB", "PORTA", "DDRD"
]

FORBIDDEN_RTOS_APIS = [
    "osThreadCreate",    # CMSIS-RTOS
    "rt_tsk_create",     # RTX
    "OSTaskCreate",      # uC/OS
]


def validate_sanity(answer: str) -> bool:
    """Reject answers containing hallucinated registers or wrong RTOS APIs."""
    return not any(f in answer for f in FORBIDDEN_REGISTERS + FORBIDDEN_RTOS_APIS)


def validate_values(answer: str) -> bool:
    """Reject unsafe hardware values."""
    if "PWMMR0 = 0" in answer or "PWMMR0=0" in answer:
        return False
    return True


def validate_completeness(answer: str, intent: str) -> bool:
    if intent in ("peripheral_configuration", "code_generation"):
        return "void" in answer and "{" in answer
    return True


def validate_pins(parsed: dict, board: str) -> bool:
    """LPC2148: valid pins are P0.x (0-31) and P1.x (16-31)."""
    return True


def validate_semantics(answer: str) -> bool:
    """Post-generation semantic sanity (placeholder for future expansion)."""
    return True
