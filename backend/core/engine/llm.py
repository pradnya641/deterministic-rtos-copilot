# -*- coding: utf-8 -*-
"""
LLM Orchestration Engine — Embedded Systems Gen-AI Assistant

Routing order:
  1. Validation   (hard-reject cross-domain traps)
  2. Intent gate  (dispatch to correct path)
  3. Deterministic knowledge lookup (GOLD_INSIGHTS)
  4. Template engine (code generation)
  5. System KB    (meta queries about this system)
  6. Hard fallback (never hallucinate)

NO LLM generation is called for hardware / RTOS / sensor queries.
"""

import re
import requests

from app.services.knowledge import check_gold_insight
from app.services.validator import validate_query
from app.services.templates import (
    get_adc_config, get_pwm_config,
    get_gpio_config, get_uart_config,
    get_spi_config, LPC2148_SPI_REGISTER_TABLE,
    get_i2c_config
)

# ==================================================================================================================─
# SYSTEM KNOWLEDGE BLOCK (about this Gen-AI system, NOT hardware)
# ==================================================================================================================─
SYSTEM_KB = {
    "hallucination": """
Hallucination = generating incorrect facts not grounded in verified data.
Prevented in this system by:
- Deterministic GOLD_INSIGHTS knowledge base (keyword + semantic matching)
- Strict cross-domain validation layer
- Hard fail-safe: no LLM generation for hardware queries
- Forbidden register list checked on all answers
""",
    "rag": """
RAG = Retrieval-Augmented Generation
- Retrieves relevant context from a vector database before generating.
- Improves factual grounding over pure LLM generation.
- Still requires a validation layer to prevent misuse or hallucinated context.
- This system prioritizes deterministic lookup over RAG for hardware facts.
""",
    "architecture": """
System Routing Architecture:
  User Query
    |
  Validation Layer  (reject cross-domain traps)
    |
  Intent Detection  (9 intent types)
    |
  +-- hardware_reasoning    -> GOLD_INSIGHTS deterministic lookup
  +-- peripheral_configuration -> Verified C template injection
  +-- rtos_architecture     -> FreeRTOS knowledge base
  +-- sensor_integration    -> Sensor datasheet knowledge base
  +-- communication_design  -> Protocol knowledge base
  +-- automotive_logic      -> ADAS / CAN knowledge base
  +-- embedded_debugging    -> Debug insight lookup
  +-- system_architecture   -> Architecture generation
  +-- system                -> This system's meta knowledge
    |
  Hard Fallback: "Information not found in provided manuals."
""",
    "deterministic": """
Deterministic Logic vs LLM for Embedded Systems:
1. Safety:      Register bits must be exactly right. LLMs hallucinate bit positions.
2. Reliability: Hardware behavior is fixed per datasheet. KB = 100% stable answer.
3. Speed:       Deterministic lookup = ~2 ms. LLM generation = 10-60 s.
4. Auditability: KB answers can be traced to source document + page number.
""",
    "intent_types": """
Supported Intent Types (9):
  1. hardware_reasoning       -- Why/how hardware behaves
  2. peripheral_configuration -- Generate verified register-level C code
  3. rtos_architecture        -- FreeRTOS tasks, queues, semaphores, scheduling
  4. sensor_integration       -- HC-SR04, LM35, MPU6050, GPS wiring + code
  5. communication_design     -- UART, SPI, I2C, CAN frame + timing
  6. automotive_logic         -- ADAS layers, BCM, telematics, sensor fusion
  7. embedded_debugging       -- Fault analysis, watchdog, stack overflow
  8. system_architecture      -- Full embedded system blueprint
  9. system                   -- Meta queries about this Gen-AI system
"""
}


def system_lookup(query: str) -> str:
    q = query.lower()
    if "hallucination" in q:                        return SYSTEM_KB["hallucination"]
    if re.search(r'\brag\b', q):                    return SYSTEM_KB["rag"]
    if "architecture" in q or "routing" in q:       return SYSTEM_KB["architecture"]
    if "deterministic" in q or "llm" in q:          return SYSTEM_KB["deterministic"]
    if "intent" in q or "intent type" in q:         return SYSTEM_KB["intent_types"]
    return "Information not found in provided manuals."


# ==================================================================================================================─
# FreeRTOS CODE TEMPLATES
# ==================================================================================================================─
FREERTOS_TASK_SKELETON = """\
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include <lpc214x.h>

/* === Queue / Semaphore handles ======================================= */
static QueueHandle_t     xSensorQueue;
static SemaphoreHandle_t xDataMutex;

/* === Task Prototypes ================================================= */
static void vAcquisitionTask(void *pvParameters);
static void vProcessingTask(void *pvParameters);
static void vActuationTask(void *pvParameters);

/* === Acquisition Task (HIGH priority) ================================ */
static void vAcquisitionTask(void *pvParameters)
{
    uint32_t sensor_val;
    for (;;)
    {
        /* Read sensor / peripheral here */
        sensor_val = 0; /* Replace with actual read */

        /* Send to processing queue (non-blocking from task) */
        xQueueSend(xSensorQueue, &sensor_val, 0);

        vTaskDelay(pdMS_TO_TICKS(50)); /* 50 ms period */
    }
}

/* === Processing Task (MEDIUM priority) =============================== */
static void vProcessingTask(void *pvParameters)
{
    uint32_t data;
    for (;;)
    {
        if (xQueueReceive(xSensorQueue, &data, portMAX_DELAY) == pdTRUE)
        {
            xSemaphoreTake(xDataMutex, portMAX_DELAY);
            /* Process data here */
            xSemaphoreGive(xDataMutex);
        }
    }
}

/* === Actuation Task (LOW priority) =================================== */
static void vActuationTask(void *pvParameters)
{
    for (;;)
    {
        xSemaphoreTake(xDataMutex, portMAX_DELAY);
        /* Apply actuation here */
        xSemaphoreGive(xDataMutex);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

/* === Main Entry ====================================================== */
int main(void)
{
    xSensorQueue = xQueueCreate(10, sizeof(uint32_t));
    xDataMutex   = xSemaphoreCreateMutex();

    xTaskCreate(vAcquisitionTask, "Acquire", 512, NULL, 3, NULL);
    xTaskCreate(vProcessingTask,  "Process", 512, NULL, 2, NULL);
    xTaskCreate(vActuationTask,   "Actuate", 256, NULL, 1, NULL);

    vTaskStartScheduler(); /* Never returns */
    for (;;);
}
"""


def get_freertos_skeleton() -> str:
    return (
        "### FreeRTOS Task Skeleton (Acquisition -> Processing -> Actuation)\n\n"
        "**Architecture:** 3-layer RTOS pipeline with queue + mutex isolation.\n\n"
        f"```c\n{FREERTOS_TASK_SKELETON}\n```\n\n"
        "**Notes:**\n"
        "- Priority 3 = Acquisition (highest — sensor deadlines must be met).\n"
        "- Priority 2 = Processing (medium).\n"
        "- Priority 1 = Actuation (lowest — safe to delay).\n"
        "- Mutex protects shared data between processing and actuation.\n"
        "- Never call `xQueueSend()` or `xSemaphoreTake()` from an ISR."
    )


# ==================================================================================================================─
# MAIN ORCHESTRATION ENGINE
# ==================================================================================================================─
def generate_answer(parsed_query: dict, context: str, board: str = "LPC2148") -> str:
    """
    Main deterministic orchestration engine.
    Validation of the generated response is handled upstream in query.py (Layer 6).
    This function ONLY generates — it does NOT pre-validate an empty string.
    """
    raw        = parsed_query["raw_query"]
    intent     = parsed_query["intent"]
    peripherals = parsed_query["peripherals"]
    sensors    = parsed_query.get("sensors", [])
    params     = parsed_query["params"]
    q          = raw.lower()

    # ══════════════════════════════════════════════════════════════════
    # STEP 1: VALIDATION — Reject cross-domain traps first (Tier 1 + Tier 2)
    # ══════════════════════════════════════════════════════════════════
    rejection = validate_query(raw)
    if not rejection:
        try:
            from app.services.validator import validate_query_semantic
            parsed_query["semantic_validator_triggered"] = True
            rejection = validate_query_semantic(raw)
        except Exception:
            pass   # semantic check unavailable — continue
    if rejection:
        parsed_query["subsystem_used"] = "Semantic Trap Rejecter"
        return rejection


    # ══════════════════════════════════════════════════════════════════
    # STEP 2: SYSTEM META QUERIES
    # ══════════════════════════════════════════════════════════════════
    if intent == "system":
        parsed_query["subsystem_used"] = "System Meta-Knowledge Base"
        return system_lookup(raw)

    # ══════════════════════════════════════════════════════════════════
    # STEP 3: HARDWARE REASONING (ADC / PWM / UART / GPIO theory)
    # ══════════════════════════════════════════════════════════════════
    if intent == "hardware_reasoning":
        parsed_query["subsystem_used"] = "Hardware Deterministic Engine"
        insight = check_gold_insight(raw)
        if insight:
            return f"{insight}\n\n---\n**Source:** Hardware Deterministic Engine"
        return "Information not found in provided manuals."

    # ══════════════════════════════════════════════════════════════════
    # STEP 4: RTOS ARCHITECTURE
    # ══════════════════════════════════════════════════════════════════
    if intent == "rtos_architecture":
        parsed_query["subsystem_used"] = "FreeRTOS Deterministic Engine"
        # ALWAYS check gold insight first — even for code requests
        insight = check_gold_insight(raw)
        if any(k in q for k in ["generate", "write", "code", "skeleton",
                                  "template", "example"]):
            skeleton = get_freertos_skeleton()
            if insight:
                primary_response = f"{insight}\n\n---\n{skeleton}"
            else:
                primary_response = skeleton
            # PATCH G: append secondary hardware_reasoning insight if relevant
            if parsed_query.get("secondary_intent") == "hardware_reasoning":
                sec_insight = check_gold_insight(raw)
                if sec_insight and sec_insight not in primary_response:
                    primary_response = f"{primary_response}\n\n---\n{sec_insight}"
            return primary_response
        if insight:
            primary_response = (f"{insight}\n\n---\n"
                                f"**Source:** FreeRTOS Deterministic Engine")
            # PATCH G: compound queries get secondary insight too
            if parsed_query.get("secondary_intent") == "hardware_reasoning":
                sec_insight = check_gold_insight(raw)
                if sec_insight and sec_insight not in primary_response:
                    primary_response = f"{primary_response}\n\n---\n{sec_insight}"
            return primary_response
        # FAISS is NOT called for rtos_architecture — use hard fallback
        return "Information not found in provided manuals."

    # ══════════════════════════════════════════════════════════════════
    # STEP 5: SENSOR INTEGRATION
    # ══════════════════════════════════════════════════════════════════
    if intent == "sensor_integration":
        parsed_query["subsystem_used"] = "Sensor Knowledge Base"
        insight = check_gold_insight(raw)
        if insight:
            return f"{insight}\n\n---\n**Source:** Sensor Knowledge Base"
        return "Information not found in provided manuals."

    # ══════════════════════════════════════════════════════════════════
    # STEP 6: COMMUNICATION DESIGN
    # ══════════════════════════════════════════════════════════════════
    if intent == "communication_design":
        parsed_query["subsystem_used"] = "Protocol Knowledge Base"
        insight = check_gold_insight(raw)
        if insight:
            return f"{insight}\n\n---\n**Source:** Protocol Knowledge Base"
        return "Information not found in provided manuals."

    # ══════════════════════════════════════════════════════════════════
    # STEP 7: AUTOMOTIVE / ADAS LOGIC
    # ══════════════════════════════════════════════════════════════════
    if intent == "automotive_logic":
        parsed_query["subsystem_used"] = "Automotive Knowledge Base"
        insight = check_gold_insight(raw)
        if insight:
            return f"{insight}\n\n---\n**Source:** Automotive Knowledge Base"
        return "Information not found in provided manuals."

    # ══════════════════════════════════════════════════════════════════
    # STEP 8: PERIPHERAL CONFIGURATION (Code templates)
    # ══════════════════════════════════════════════════════════════════
    if intent == "peripheral_configuration":
        parsed_query["subsystem_used"] = "Peripheral Config Template Engine"
        # FreeRTOS code requested alongside peripheral
        if "freertos" in q or "rtos" in q or "task" in q:
            return get_freertos_skeleton()

        # Multi-peripheral stitching
        if len(peripherals) > 1:
            codes = []
            for p in peripherals:
                if p == "ADC":
                    codes.append(get_adc_config(params["channel"]))
                elif p == "UART":
                    codes.append(get_uart_config(0, params["baud"]))
                elif p == "PWM":
                    codes.append(get_pwm_config(params["channel"], params["duty"]))
                elif p == "SPI":
                    codes.append(get_spi_config())
                elif p == "I2C":
                    codes.append(get_i2c_config())
            return (
                "### Multi-Module Configuration\n\n"
                "**Verified C Implementation:**\n"
                f"```c\n" + "\n".join(codes) + "\n```"
            )

        # Single peripheral
        if len(peripherals) == 1:
            p = peripherals[0]
            insight = check_gold_insight(raw, allow_semantic=False)
            insight_prefix = f"{insight}\n\n" if insight else ""
            
            if p == "ADC":
                return insight_prefix + (
                    "### ADC Configuration\n\n"
                    f"**Verified C Implementation:**\n```c\n{get_adc_config(params['channel'])}\n```\n\n"
                    "**Register:** AD0CR — SEL, CLKDIV, PDN, START bits must all be set correctly."
                )
            elif p == "UART":
                return insight_prefix + (
                    "### UART Configuration\n\n"
                    f"**Verified C Implementation:**\n```c\n{get_uart_config(0, params['baud'])}\n```\n\n"
                    "**Critical:** DLAB must be cleared after baud rate setup (UxLCR bit 7 = 0)."
                )
            elif p == "PWM":
                return insight_prefix + (
                    "### PWM Configuration\n\n"
                    f"**Verified C Implementation:**\n```c\n{get_pwm_config(params['channel'], params['duty'])}\n```\n\n"
                    "**Rule:** PWMMR0 must be > 0. PWMMR1 must be ≤ PWMMR0."
                )
            elif p == "GPIO":
                return insight_prefix + (
                    "### GPIO Configuration\n\n"
                    "**Pattern:**\n```c\n"
                    "#include <lpc214x.h>\n"
                    "IO0DIR |= (1 << 10);   /* P0.10 as output */\n"
                    "IO0SET  = (1 << 10);   /* Set HIGH */\n"
                    "IO0CLR  = (1 << 10);   /* Set LOW  */\n"
                    "```"
                )
            elif p == "SPI":
                return insight_prefix + (
                    "### SPI Configuration\n\n"
                    f"**Verified C Implementation:**\n```c\n{get_spi_config()}\n```\n\n"
                    f"**Register Reference:**\n{LPC2148_SPI_REGISTER_TABLE}\n\n"
                    "**Rule:** S0SPCCR must be an even number ≥ 8. S0SPCR MSTR=1 for master mode."
                )
            elif p == "I2C":
                return insight_prefix + (
                    "### I2C Configuration\n\n"
                    f"**Verified C Implementation:**\n```c\n{get_i2c_config()}\n```\n\n"
                    "**Rule:** I20CONSET I2EN bit (bit 6) must be set to enable I2C. SCLH+SCLL = PCLK / I2C_freq."
                )

        # Fallback if peripheral matched but no template exists
        insight = check_gold_insight(raw)
        if insight:
            return f"{insight}\n\n---\n**Source:** Protocol Knowledge Base"

        return "### Query Unclear\nSpecify peripheral: ADC / UART / PWM / GPIO / SPI / I2C."

    # ══════════════════════════════════════════════════════════════════
    # STEP 9: EMBEDDED DEBUGGING
    # ══════════════════════════════════════════════════════════════════
    if intent == "embedded_debugging":
        parsed_query["subsystem_used"] = "Embedded Debug Knowledge Base"
        insight = check_gold_insight(raw)
        if insight:
            return f"{insight}\n\n---\n**Source:** Embedded Debug Knowledge Base"
        return (
            "### Debugging Guidance\n"
            "To diagnose this issue:\n"
            "1. Verify register configuration matches datasheet values.\n"
            "2. Check PINSEL is correctly set for the peripheral in use.\n"
            "3. Verify PCLK divider is within peripheral specifications.\n"
            "4. For RTOS issues: check stack size, priority levels, and ISR safety.\n\n"
            "If the problem persists, provide the register values for deeper analysis."
        )

    # ══════════════════════════════════════════════════════════════════
    # STEP 10: SYSTEM ARCHITECTURE GENERATION
    # ══════════════════════════════════════════════════════════════════
    if intent == "system_architecture":
        parsed_query["subsystem_used"] = "Architecture Knowledge Base"
        insight = check_gold_insight(raw)
        if insight:
            return f"{insight}\n\n---\n**Source:** Architecture Knowledge Base"
        return (
            "### System Architecture Template\n\n"
            "**Layers:**\n"
            "1. **Acquisition** — Sensor reading (ADC / UART / SPI / I2C)\n"
            "2. **Processing**  — Data validation, filtering, fusion\n"
            "3. **Actuation**   — PWM / GPIO / CAN output\n"
            "4. **Communication** — UART / CAN telemetry\n\n"
            "**RTOS Structure:**\n"
            "- Use FreeRTOS queues between layers.\n"
            "- High-priority task = acquisition.\n"
            "- Low-priority task = logging / display.\n\n"
            "Specify your sensor and peripheral set for a detailed blueprint."
        )

    # ══════════════════════════════════════════════════════════════════
    # DEFAULT FALLBACK — never hallucinate
    # ══════════════════════════════════════════════════════════════════
    parsed_query["subsystem_used"] = "Default Fallback Handler"
    return "### Query Unclear\nPlease specify the domain: hardware / RTOS / sensor / protocol / automotive."
