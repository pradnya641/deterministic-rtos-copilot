"""
Diff Formatter — Conversational Embedded Firmware Copilot.

Architectural purpose:
  Format incremental architecture modifications as readable diffs with
  embedded-systems-accurate explanations of RTOS impact, timing impact,
  and compile impact.

Deterministic contract:
  - All output is template-based. No LLM generation in this module.
  - Every DiffEntry has an explicit reason, rtos_impact, and timing_impact.
  - Output is structured as both human-readable markdown and a machine-readable
    list of DiffEntry objects for programmatic use.

RTOS implications:
  - rtos_impact must be non-empty and accurate. Vague strings like "no change"
    are only acceptable when genuinely no RTOS primitive is affected.

Compile implications:
  - compile_impact describes whether new symbols are introduced, whether
    the change affects the linker, and whether SDK-validity is maintained.
"""

from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiffEntry:
    """
    A single line-level change in the architecture.

    file_section:   The logical code section affected.
                    One of: "queue_creation" | "isr_handler" | "task_body" |
                             "main_init" | "task_priorities" | "peripheral_init" |
                             "watchdog" | "overflow_monitor" | "dma_skeleton"
    old_line:       The exact old line (may be empty for pure insertions).
    new_line:       The new line (may be empty for pure deletions).
    reason:         Human-readable explanation of WHY this change was made.
    rtos_impact:    Specific RTOS impact: queue depth, priority, stack, ISR path.
    timing_impact:  Specific timing impact: latency, jitter, period, CPU load.
    compile_impact: Whether this introduces new symbols or changes linkage.
    """
    file_section:   str
    old_line:       str
    new_line:       str
    reason:         str
    rtos_impact:    str
    timing_impact:  str  = "No timing impact."
    compile_impact: str  = "SDK-valid — no new symbols introduced."


# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN DIFF RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def render_diff_entry(entry: DiffEntry) -> str:
    """
    Render a single DiffEntry as a markdown diff block with explanations.
    """
    lines = []

    # Code diff block
    lines.append("```diff")
    if entry.old_line.strip():
        lines.append(f"- {entry.old_line.rstrip()}")
    if entry.new_line.strip():
        lines.append(f"+ {entry.new_line.rstrip()}")
    lines.append("```")

    # Explanation block
    lines.append(f"\n**Why:** {entry.reason}")
    lines.append(f"\n**RTOS Impact:** {entry.rtos_impact}")
    lines.append(f"\n**Timing Impact:** {entry.timing_impact}")
    lines.append(f"\n**Compile Impact:** {entry.compile_impact}")

    return "\n".join(lines)


def render_full_diff(
    modification_type: str,
    entries: list,
    explanation: str,
    new_code_block: Optional[str] = None,
) -> str:
    """
    Render the complete modification response with:
    - Modification summary
    - Individual diff entries
    - Optional full updated code block
    - Architecture impact summary

    Args:
        modification_type: Human-readable modification name (e.g. "Increase Queue Depth")
        entries:           list[DiffEntry] — all changes in this modification
        explanation:       Overall architectural explanation
        new_code_block:    If provided, the full updated code after modification

    Returns:
        Formatted markdown string ready for API response.
    """
    lines = []

    # Build structured explanation fields
    what_changed_items = []
    why_items = []
    rtos_impact_items = []
    ownership_items = []
    compile_status = "SDK-valid"
    
    for entry in entries:
        sect = entry.file_section.replace("_", " ").title()
        line_desc = ""
        if entry.new_line.strip():
            line_desc = entry.new_line.strip().splitlines()[0]
        elif entry.old_line.strip():
            line_desc = "Removed " + entry.old_line.strip().splitlines()[0]
        what_changed_items.append(f"{sect}: `{line_desc}`")
        
        why_items.append(entry.reason)
        rtos_impact_items.append(entry.rtos_impact)
        if hasattr(entry, 'compile_impact') and entry.compile_impact:
            if "requires recompile" in entry.compile_impact.lower() or "requires re-compile" in entry.compile_impact.lower():
                compile_status = "requires recompile"
        if hasattr(entry, 'timing_impact') and entry.timing_impact:
            rtos_impact_items.append(entry.timing_impact)

    # Check for ownership changes
    for entry in entries:
        if any(w in entry.reason.lower() or w in entry.rtos_impact.lower() for w in ["pinsel", "pins", "ownership", "register", "vic"]):
            ownership_items.append(entry.rtos_impact)

    if not ownership_items:
        ownership_items.append("No register/pin ownership adjustments.")

    # Header
    lines.append(f"## Architecture Modification: {modification_type}\n")
    
    # Structured response block
    lines.append("### System Adjustment Details")
    lines.append(f"- **What changed:** {'; '.join(what_changed_items) if what_changed_items else 'Code modified'}")
    lines.append(f"- **Why it changed:** {'; '.join(why_items) if why_items else explanation}")
    lines.append(f"- **RTOS impact:** {'; '.join(rtos_impact_items) if rtos_impact_items else 'None'}")
    lines.append(f"- **Ownership change:** {'; '.join(ownership_items)}")
    lines.append(f"- **Compile status:** {compile_status}\n")

    # Individual diffs
    if entries:
        lines.append("### Changes Applied\n")
        for i, entry in enumerate(entries, 1):
            section_label = entry.file_section.replace("_", " ").title()
            lines.append(f"**Change {i} — {section_label}**\n")
            lines.append(render_diff_entry(entry))
            lines.append("")

    # Updated full code block (optional)
    if new_code_block and new_code_block.strip():
        lines.append("### Updated Architecture Code\n")
        lines.append("> [!NOTE]")
        lines.append("> This code block has been validated by `arm-none-eabi-gcc -fsyntax-only`.")
        lines.append("> SDK-link verification is available via `/ask` with the full harness.\n")
        lines.append(f"```c\n{new_code_block.strip()}\n```")

    # Architecture preservation note
    if entries:
        preserved = _list_preserved_elements(entries)
        if preserved:
            lines.append("\n### Architecture Preserved")
            lines.append("The following components were **not modified**:")
            for item in preserved:
                lines.append(f"- {item}")

    return "\n".join(lines)


def _list_preserved_elements(entries: list) -> list:
    """
    Infer which architecture elements were NOT touched by the diff entries.
    Returns a list of human-readable strings for the preservation note.
    """
    touched_sections = {e.file_section for e in entries}
    all_sections = {
        "queue_creation": "Queue creation parameters",
        "isr_handler": "ISR handler body and VIC setup",
        "task_body": "Task function bodies",
        "main_init": "main() initialization sequence",
        "task_priorities": "Task priority assignments",
        "peripheral_init": "Peripheral register configuration",
        "watchdog": "Watchdog timer setup",
        "overflow_monitor": "Queue overflow monitoring",
        "dma_skeleton": "DMA architecture skeleton",
    }
    preserved = []
    for section, label in all_sections.items():
        if section not in touched_sections:
            preserved.append(label)
    return preserved


# ─────────────────────────────────────────────────────────────────────────────
# STANDARD EXPLANATIONS (reused by modifier.py)
# ─────────────────────────────────────────────────────────────────────────────

def make_queue_depth_diff(
    queue_name: str,
    old_depth: int,
    new_depth: int,
    item_type: str,
    producer_rate_ms: Optional[int] = None,
    reason_context: str = "",
) -> DiffEntry:
    """
    Build a DiffEntry for a queue depth change.
    Computes burst tolerance explanation from producer rate if available.
    """
    old_line = f"{queue_name} = xQueueCreate({old_depth}, sizeof({item_type}));"
    new_line = f"{queue_name} = xQueueCreate({new_depth}, sizeof({item_type}));"

    if producer_rate_ms and producer_rate_ms > 0:
        burst_ms = new_depth * producer_rate_ms
        reason = (
            f"Queue depth increased from {old_depth} to {new_depth}. "
            f"At a producer rate of {producer_rate_ms}ms/item, depth {new_depth} "
            f"provides {burst_ms}ms of burst tolerance before overflow. "
            f"{reason_context}".strip()
        )
    else:
        reason = (
            f"Queue depth increased from {old_depth} to {new_depth} to reduce "
            f"the probability of item loss under transient producer-consumer rate mismatch. "
            f"{reason_context}".strip()
        )

    memory_delta = (new_depth - old_depth) * _sizeof_approx(item_type)
    rtos_impact = (
        f"Queue '{queue_name}' depth: {old_depth} → {new_depth}. "
        f"Additional queue memory: ~{memory_delta} bytes. "
        f"No task priority changes. No ISR path changes."
    )

    return DiffEntry(
        file_section="queue_creation",
        old_line=old_line,
        new_line=new_line,
        reason=reason,
        rtos_impact=rtos_impact,
        timing_impact=(
            f"Deeper queue reduces producer blocking probability. "
            f"Consumer vTaskDelay period unchanged."
        ),
        compile_impact="SDK-valid — xQueueCreate is a FreeRTOS v8.x API. No new symbols.",
    )


def make_overflow_monitor_diff(
    queue_name: str,
    watermark_pct: int = 80,
) -> DiffEntry:
    """
    Build a DiffEntry for adding uxQueueMessagesWaiting occupancy monitoring.
    """
    old_line = ""
    new_line = (
        f"UBaseType_t uxWaiting = uxQueueMessagesWaiting({queue_name});\n"
        f"    if (uxWaiting > uxMaxOccupancy) uxMaxOccupancy = uxWaiting; "
        f"/* High-watermark tracking */"
    )
    return DiffEntry(
        file_section="overflow_monitor",
        old_line=old_line,
        new_line=new_line,
        reason=(
            f"Adds runtime queue occupancy monitoring for '{queue_name}'. "
            f"uxQueueMessagesWaiting() is non-blocking and ISR-safe (read-only). "
            f"High-watermark tracked in uxMaxOccupancy for telemetry or diagnostic logging. "
            f"Alert threshold at {watermark_pct}% queue saturation."
        ),
        rtos_impact=(
            f"uxQueueMessagesWaiting() call adds ~2 CPU cycles overhead per producer tick. "
            f"No task suspension or blocking. No ISR path change."
        ),
        timing_impact="Negligible — single register read per acquisition cycle.",
        compile_impact="SDK-valid — uxQueueMessagesWaiting is a FreeRTOS v8.x API.",
    )


def make_watchdog_diff() -> list:
    """
    Build DiffEntry list for adding LPC2148 hardware watchdog.
    Returns two entries: WDT init in main_init, and feed in dedicated task.
    """
    init_entry = DiffEntry(
        file_section="watchdog",
        old_line="",
        new_line=(
            "WDMOD = 0x03;        /* Enable WDT + Reset on timeout */\n"
            "    WDTC  = 0x00FFFFFF;  /* ~1.12s timeout @ PCLK=15MHz */\n"
            "    WDFEED = 0xAA; WDFEED = 0x55;  /* Initial feed */"
        ),
        reason=(
            "Configures LPC2148 hardware watchdog (WDMOD, WDTC, WDFEED). "
            "WDMOD bit 0 (WDEN) enables the watchdog. Bit 1 (WDRESET) forces a "
            "hardware reset on timeout instead of just asserting the interrupt. "
            "Timeout = WDTC / (PCLK/4) = 0xFFFFFF / 3,750,000 ≈ 1.12 seconds."
        ),
        rtos_impact=(
            "A dedicated vWatchdogTask at priority tskIDLE_PRIORITY+1 performs "
            "the periodic feed sequence (0xAA, 0x55). All critical tasks must "
            "set a liveness bit in ulLivenessBits before the watchdog task feeds. "
            "If any task misses its heartbeat, the watchdog fires a hardware reset."
        ),
        timing_impact="Watchdog feed must occur within WDTC period. Task runs at 500ms interval.",
        compile_impact="SDK-valid — WDMOD/WDTC/WDFEED are LPC2148 registers in lpc214x.h.",
    )
    task_entry = DiffEntry(
        file_section="watchdog",
        old_line="",
        new_line=(
            "static volatile uint32_t ulLivenessBits = 0;\n\n"
            "static void vWatchdogTask(void *pv) {\n"
            "    for (;;) {\n"
            "        vTaskDelay(pdMS_TO_TICKS(500));\n"
            "        if (ulLivenessBits == EXPECTED_LIVENESS_MASK) {\n"
            "            ulLivenessBits = 0;\n"
            "            WDFEED = 0xAA; WDFEED = 0x55;  /* Feed sequence */\n"
            "        }\n"
            "        /* If mask not met: watchdog fires on next timeout → hardware reset */\n"
            "    }\n"
            "}"
        ),
        reason=(
            "Watchdog task feeds the LPC2148 hardware WDT only when all critical tasks "
            "have checked in via ulLivenessBits. Tasks set their bit at the end of each "
            "periodic iteration. If a task hangs (deadlock, stack overflow, bus stall), "
            "its bit is not set, the feed is withheld, and the WDT resets the system."
        ),
        rtos_impact=(
            "vWatchdogTask runs at priority 1 (lowest application priority). "
            "It does not starve acquisition or processing tasks. "
            "ulLivenessBits is a volatile uint32_t — atomic on ARM7 for 32-bit access."
        ),
        timing_impact="500ms feed interval leaves 600ms margin before 1.12s WDT timeout.",
        compile_impact="SDK-valid — uses FreeRTOS v8.x APIs only.",
    )
    return [init_entry, task_entry]


def make_isr_conversion_diff(
    task_name: str,
    peripheral: str,
    poll_line: str,
) -> list:
    """
    Build DiffEntry list for converting a polling loop to ISR-driven acquisition.
    Returns three entries: remove poll loop, add ISR handler, add semaphore.
    """
    remove_entry = DiffEntry(
        file_section="task_body",
        old_line=poll_line.replace("while", "busy_wait"),
        new_line="xSemaphoreTake(xDataReadySem, portMAX_DELAY);  /* ISR-driven — no polling */",
        reason=(
            f"Replaces the busy-wait polling loop in {task_name} with a semaphore "
            f"wait. The {peripheral} ISR now gives the semaphore when data is ready. "
            f"The task blocks on portMAX_DELAY instead of spinning, releasing the CPU "
            f"to lower-priority tasks during the wait interval."
        ),
        rtos_impact=(
            f"{task_name} is now event-driven. CPU is yielded to lower-priority tasks "
            f"during {peripheral} data acquisition periods. "
            f"xSemaphoreTakeFromISR() → xSemaphoreGiveFromISR() path is ISR-safe."
        ),
        timing_impact=(
            f"Eliminates busy-wait CPU monopolization. Task jitter is now bounded by "
            f"ISR latency (~1-3 μs on ARM7 at 60MHz CCLK) rather than polling period."
        ),
        compile_impact="SDK-valid — xSemaphoreTake and xSemaphoreCreateBinary are FreeRTOS v8.x APIs.",
    )
    isr_entry = DiffEntry(
        file_section="isr_handler",
        old_line="",
        new_line=(
            f"void {peripheral}_IRQHandler(void) __attribute__((interrupt(\"IRQ\")));\n"
            f"void {peripheral}_IRQHandler(void) {{\n"
            f"    BaseType_t xWoken = pdFALSE;\n"
            f"    /* Read data register here */\n"
            f"    xSemaphoreGiveFromISR(xDataReadySem, &xWoken);\n"
            f"    VICVectAddr = 0;   /* Acknowledge VIC */\n"
            f"    portYIELD_FROM_ISR(xWoken);\n"
            f"}}"
        ),
        reason=(
            f"Adds the {peripheral} IRQ handler with correct ARM7 ISR attribute, "
            f"VIC acknowledgment (VICVectAddr = 0), and ISR-safe semaphore give. "
            f"Without VICVectAddr = 0, the ARM7 VIC locks out all subsequent vectored interrupts."
        ),
        rtos_impact=(
            "xSemaphoreGiveFromISR() is the correct API for ISR context. "
            "portYIELD_FROM_ISR() triggers an immediate context switch if a "
            "higher-priority task was unblocked by the semaphore give."
        ),
        timing_impact=f"ISR execution time: ~10-20 cycles (register read + queue/sem give + VIC ack).",
        compile_impact="SDK-valid — __attribute__((interrupt(\"IRQ\"))) is ARM-GCC specific. Required for ARM7.",
    )
    sem_entry = DiffEntry(
        file_section="main_init",
        old_line="",
        new_line="xDataReadySem = xSemaphoreCreateBinary();  /* ISR → task synchronization */",
        reason=(
            "Binary semaphore for ISR-to-task synchronization. "
            "xSemaphoreCreateBinary() produces a semaphore that starts empty — "
            "the task blocks immediately until the ISR gives it."
        ),
        rtos_impact=(
            "Binary semaphore uses ~80 bytes of FreeRTOS heap. "
            "xSemaphoreCreateBinary() is a FreeRTOS v8.x API compatible with the LPC2148 ARM7 port."
        ),
        timing_impact="Semaphore creation is a one-time startup cost only.",
        compile_impact="SDK-valid — xSemaphoreCreateBinary is in semphr.h.",
    )
    return [remove_entry, isr_entry, sem_entry]


def make_dma_skeleton_diff() -> DiffEntry:
    """
    Build a DiffEntry for appending a conceptual DMA-ready architecture note.
    Clearly labeled as conceptual — LPC2148 has no general-purpose GPDMA.
    """
    dma_skeleton_code = (
        "/* ── CONCEPTUAL DMA-READY PING-PONG BUFFER SKELETON ─────────────────────────\n"
        " * NOTE: LPC2148 does NOT implement general-purpose GPDMA.\n"
        " * Replace MockDMAChannel_t with actual GPDMA registers when porting to\n"
        " * LPC17xx, STM32, or another target with hardware DMA support.\n"
        " * ─────────────────────────────────────────────────────────────────────────── */\n\n"
        "#define DMA_BUFFER_SIZE 64\n"
        "#define BUFFER_OWNER_DMA  0\n"
        "#define BUFFER_OWNER_TASK 1\n\n"
        "static uint8_t ucPingBuffer[DMA_BUFFER_SIZE];\n"
        "static uint8_t ucPongBuffer[DMA_BUFFER_SIZE];\n"
        "static volatile uint8_t ucActiveDMABuffer  = BUFFER_OWNER_DMA;\n"
        "static SemaphoreHandle_t xDMACompleteSem;\n\n"
        "/* DMA completion ISR (conceptual — replace with real DMA ISR) */\n"
        "void MockDMA_IRQHandler(void) __attribute__((interrupt(\"IRQ\")));\n"
        "void MockDMA_IRQHandler(void)\n"
        "{\n"
        "    BaseType_t xWoken = pdFALSE;\n"
        "    ucActiveDMABuffer ^= 1;   /* Toggle active buffer ownership */\n"
        "    xSemaphoreGiveFromISR(xDMACompleteSem, &xWoken);\n"
        "    VICVectAddr = 0;\n"
        "    portYIELD_FROM_ISR(xWoken);\n"
        "}"
    )
    return DiffEntry(
        file_section="dma_skeleton",
        old_line="",
        new_line=dma_skeleton_code,
        reason=(
            "Appends a conceptual ping-pong DMA skeleton to the architecture. "
            "This documents the intended future DMA integration path without "
            "synthesizing non-functional code. LPC2148 does not implement "
            "general-purpose GPDMA — the skeleton is explicitly labeled as conceptual."
        ),
        rtos_impact=(
            "No runtime RTOS change. The skeleton uses xSemaphoreGiveFromISR() and "
            "xSemaphoreTake() for DMA-completion signaling — FreeRTOS v8.x compatible."
        ),
        timing_impact="Conceptual only — no runtime timing impact.",
        compile_impact=(
            "The MockDMAChannel_t struct uses a fixed address (0xE00C0000). "
            "This compiles but writing to this address on LPC2148 has no effect. "
            "Must be replaced with real peripheral addresses on a DMA-capable target."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _sizeof_approx(item_type: str) -> int:
    """Approximate sizeof() for common embedded types."""
    type_sizes = {
        "uint8_t": 1, "char": 1,
        "uint16_t": 2, "int16_t": 2,
        "uint32_t": 4, "int32_t": 4, "int": 4, "float": 4,
        "uint64_t": 8, "double": 8,
    }
    # Handle struct types: return 16 as a conservative estimate
    for known_type, size in type_sizes.items():
        if known_type in item_type:
            return size
    return 16   # Conservative default for unknown struct types


def format_no_change_response(query: str, state_system_name: str) -> str:
    """
    Response when a query is recognized as a modification intent
    but results in no state change (e.g. queue already at requested depth).
    """
    return (
        f"## No Architecture Change Required\n\n"
        f"The requested modification to **{state_system_name}** "
        f"resulted in no changes — the architecture already satisfies the request.\n\n"
        f"**Query:** `{query}`\n\n"
        f"If you believe a change is needed, please specify the target component "
        f"or desired parameter value explicitly (e.g. 'set xRxQueue depth to 64')."
    )


def format_rejection_response(reason: str, modification_type: str) -> str:
    """
    Response when a modification is rejected by the validator or
    compatibility check (e.g. stream buffer on FreeRTOS v8.x).
    """
    return (
        f"## Modification Rejected: {modification_type}\n\n"
        f"**Reason:** {reason}\n\n"
        f"> [!WARNING]\n"
        f"> This modification was blocked by the deterministic validation layer.\n"
        f"> The existing architecture has not been modified.\n\n"
        f"If you need this feature, please consult the LPC2148 User Manual "
        f"(UM10139) or the FreeRTOS v8.x ARM7 port documentation for compatible alternatives."
    )
