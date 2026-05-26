"""
Conversation State Manager — Deterministic Embedded Firmware Copilot.

Architectural purpose:
  Persists architecture state (tasks, queues, ISR topology, peripherals,
  generated code) across conversational turns within a session.

Deterministic contract:
  - State updates are atomic dict assignments — no partial writes.
  - Peripheral ownership is tracked at register level to prevent
    silent PINSEL / VIC conflicts when modifiers add new peripherals.
  - Sessions are evicted lazily after TTL_SECONDS (no background thread).
  - Bounded by MAX_SESSIONS to prevent unbounded memory growth.

RTOS implications:
  - freertos_version is stored per session and enforced by modifier.py
    to reject FreeRTOS v10+ APIs (e.g. stream buffers) on the LPC2148 port.
  - ISR topology tracks VIC channel assignments to detect conflicts.

Validation strategy:
  - check_peripheral_conflict() must be called by modifier.py before
    every peripheral-modifying operation.
  - No external DB dependency — all state is in-process (in-memory dict).
    State is lost on server restart. Document this clearly in API responses.

Compiler implications:
  - The generated_code field holds the last SDK-valid synthesized code block.
  - Modifier patches are applied against this field, then revalidated.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
MAX_SESSIONS = 1000          # Hard cap — oldest session evicted when exceeded
TTL_SECONDS  = 7200          # 2 hours idle → lazy eviction
MAX_TURN_HISTORY = 20        # Keep last 20 turns per session


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PeripheralOwnership:
    """
    Register-level peripheral ownership record.
    Tracks which task owns a peripheral and which PINSEL bits it uses,
    so that modifier.py can detect silent conflicts before patching.
    """
    peripheral:  str    # "UART0", "SPI0", "ADC0", "PWM1", "CAN1"
    owner_task:  str    # Task name that configured this peripheral
    pinsel_reg:  str    # "PINSEL0" or "PINSEL1"
    pinsel_bits: str    # "1:0", "15:14", "25:24" (human-readable range)
    pinsel_val:  int    # Bit value written (e.g. 1 for UART, 2 for PWM)
    vic_channel: Optional[int] = None  # VIC vectored channel, if ISR-driven


@dataclass
class ArchitectureNode:
    """
    Node in the architecture graph.
    Represents a task, queue, ISR, semaphore, mutex, or peripheral.
    Edges represent producer→consumer or owner→owned relationships.
    """
    name:           str         # "xRxQueue", "UART0_ISR", "vParserTask"
    node_type:      str         # "queue" | "isr" | "task" | "semaphore" | "mutex" | "peripheral"
    connections_to: list = field(default_factory=list)   # list[str] downstream node names
    metadata:       dict = field(default_factory=dict)   # depth, priority, period_ms, etc.


@dataclass
class ConversationState:
    """
    Full architecture state for one conversational session.

    Design intent:
      Every field maps to a concrete embedded system property.
      There are no generic "memory" or "history" blobs —
      each piece of state has a deterministic role in the modifier.
    """
    session_id:          str
    system_name:         str          = "Unnamed System"
    freertos_version:    str          = "8.x"     # LPC2148 ARM7 port — v8.x only
    board:               str          = "LPC2148"

    # ── RTOS Objects ───────────────────────────────────────────────────
    tasks:               list         = field(default_factory=list)
    # Each task: {"name": str, "priority": int, "period_ms": int,
    #              "stack_words": int, "role": str}

    queues:              list         = field(default_factory=list)
    # Each queue: {"name": str, "depth": int, "item_type": str,
    #               "from_task": str, "to_task": str}

    semaphores:          list         = field(default_factory=list)   # list[str] names
    mutexes:             list         = field(default_factory=list)   # list[str] names
    binary_semaphores:   list         = field(default_factory=list)   # list[str] names
    counting_semaphores: list         = field(default_factory=list)   # list[str] names

    # ── ISR Topology ───────────────────────────────────────────────────
    isr_topology:        list         = field(default_factory=list)
    # Each ISR: {"isr_name": str, "vic_channel": int, "handler_fn": str,
    #             "queue_name": str, "peripheral": str}

    # ── Peripheral Ownership ───────────────────────────────────────────
    peripherals:         dict         = field(default_factory=dict)
    # key = peripheral name (e.g. "UART0"), value = PeripheralOwnership

    # ── Timing Assumptions ─────────────────────────────────────────────
    timing_assumptions:  dict         = field(default_factory=lambda: {
        "PCLK_Hz":  15_000_000,      # PCLK = CCLK/4 = 60MHz/4 = 15MHz
        "CCLK_Hz":  60_000_000,      # PLL at 60MHz
        "VPBDIV":   4,
        "tick_rate_hz": 1000,        # configTICK_RATE_HZ default
    })

    # ── Derived Quick-Access ───────────────────────────────────────────
    queue_depths:        dict         = field(default_factory=dict)    # name → int
    task_priorities:     dict         = field(default_factory=dict)    # name → int

    # ── Generated Code ─────────────────────────────────────────────────
    generated_code:      str          = ""    # last SDK-valid synthesized code block

    # ── Architecture Summary ───────────────────────────────────────────
    architecture_summary: str          = ""

    # ── Architecture Graph ──────────────────────────────────────────────
    architecture_graph:  list         = field(default_factory=list)    # list[ArchitectureNode]

    # ── Turn History ───────────────────────────────────────────────────
    turn_history:        list         = field(default_factory=list)
    # Each turn: {"turn": int, "query": str, "modification_type": str|None,
    #              "diff_summary": str, "timestamp": float}
    turn_count:          int          = 0

    # ── Lifecycle ──────────────────────────────────────────────────────
    created_at:          float        = field(default_factory=time.time)
    last_modified:       float        = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY SESSION STORE
# ─────────────────────────────────────────────────────────────────────────────

_sessions: dict[str, ConversationState] = {}


def _evict_expired() -> None:
    """
    Lazy TTL eviction — called on every read/write operation.
    Removes sessions older than TTL_SECONDS.
    Also enforces MAX_SESSIONS by evicting the oldest session when full.
    No background thread required.
    """
    now = time.time()
    expired = [sid for sid, s in _sessions.items()
               if (now - s.last_modified) > TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]
        logger.debug(f"[SESSION] Evicted expired session: {sid}")

    # Hard cap: remove oldest session if at limit
    while len(_sessions) >= MAX_SESSIONS:
        oldest_sid = min(_sessions, key=lambda s: _sessions[s].last_modified)
        del _sessions[oldest_sid]
        logger.warning(f"[SESSION] MAX_SESSIONS reached — evicted oldest: {oldest_sid}")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_session(session_id: str) -> Optional[ConversationState]:
    """
    Retrieve an existing session by ID.
    Returns None if session does not exist or has expired.
    """
    _evict_expired()
    return _sessions.get(session_id)


def create_session(session_id: str) -> ConversationState:
    """
    Create a new empty conversation session.
    Overwrites an existing session with the same ID.
    """
    _evict_expired()
    state = ConversationState(session_id=session_id)
    _sessions[session_id] = state
    logger.info(f"[SESSION] Created new session: {session_id}")
    return state


def update_session(session_id: str, state: ConversationState) -> None:
    """
    Persist an updated ConversationState back to the store.
    Updates last_modified timestamp atomically.
    """
    state.last_modified = time.time()
    _sessions[session_id] = state


def delete_session(session_id: str) -> bool:
    """
    Explicitly delete a session. Returns True if it existed.
    """
    existed = session_id in _sessions
    _sessions.pop(session_id, None)
    if existed:
        logger.info(f"[SESSION] Deleted session: {session_id}")
    return existed


def get_or_create_session(session_id: str) -> ConversationState:
    """
    Convenience: get existing session or create a fresh one.
    """
    existing = get_session(session_id)
    if existing is not None:
        return existing
    return create_session(session_id)


def session_count() -> int:
    """Return number of active sessions (for observability)."""
    return len(_sessions)


# ─────────────────────────────────────────────────────────────────────────────
# PERIPHERAL CONFLICT DETECTION
# ─────────────────────────────────────────────────────────────────────────────

# Known PINSEL bit ranges per peripheral — used for conflict detection.
# Source: LPC2148 User Manual UM10139, Chapter 8 (Pin Connect Block).
_PERIPHERAL_PINSEL_MAP: dict[str, dict] = {
    "UART0":  {"reg": "PINSEL0", "bits": "1:0",   "val": 1},
    "UART1":  {"reg": "PINSEL0", "bits": "19:16",  "val": 1},
    "PWM1":   {"reg": "PINSEL0", "bits": "1:0",   "val": 2},
    "PWM2":   {"reg": "PINSEL0", "bits": "15:14", "val": 2},
    "SPI0":   {"reg": "PINSEL0", "bits": "15:8",  "val": 1},
    "I2C0":   {"reg": "PINSEL0", "bits": "7:4",   "val": 1},
    "ADC0_1": {"reg": "PINSEL1", "bits": "25:24", "val": 1},
    "ADC0_2": {"reg": "PINSEL1", "bits": "27:26", "val": 1},
    "CAN1":   {"reg": "PINSEL0", "bits": "3:0",   "val": 1},
    "LCD":    {"reg": "PINSEL0", "bits": "31:20", "val": 0},
}

# Peripherals that share the same PINSEL bits (cannot coexist).
_PINSEL_CONFLICTS: list[tuple[str, str]] = [
    ("UART0", "PWM1"),    # Both use PINSEL0 bits[1:0]
    ("UART0", "CAN1"),    # CAN1 bits[3:0] overlaps UART0 bits[1:0]
    ("SPI0",  "PWM2"),    # Both use PINSEL0 bits[15:14]
]


def check_peripheral_conflict(
    state: ConversationState,
    new_peripheral: str,
    requesting_task: str,
) -> Optional[str]:
    """
    Check if adding `new_peripheral` would conflict with any already-owned
    peripheral in the session state.

    Returns:
        None if no conflict.
        A human-readable conflict description string if conflict detected.

    Called by modifier.py before every peripheral-modifying operation.

    Architectural contract:
        This function is DETERMINISTIC — same inputs always produce same output.
        It does NOT modify state.
    """
    # Check direct ownership conflict (same peripheral owned by different task)
    if new_peripheral in state.peripherals:
        existing = state.peripherals[new_peripheral]
        if existing.owner_task != requesting_task:
            return (
                f"Peripheral conflict: '{new_peripheral}' is already owned by "
                f"task '{existing.owner_task}' "
                f"(PINSEL {existing.pinsel_reg} bits {existing.pinsel_bits} = {existing.pinsel_val}). "
                f"Task '{requesting_task}' cannot claim it without releasing the existing owner."
            )
        return None   # Same task reconfiguring — allowed

    # Check PINSEL bit-level conflicts with existing peripherals
    for (p1, p2) in _PINSEL_CONFLICTS:
        if new_peripheral == p1 and p2 in state.peripherals:
            existing = state.peripherals[p2]
            return (
                f"PINSEL conflict: '{new_peripheral}' and '{p2}' share PINSEL bits "
                f"({existing.pinsel_reg} {existing.pinsel_bits}). "
                f"They cannot be active simultaneously on LPC2148."
            )
        if new_peripheral == p2 and p1 in state.peripherals:
            existing = state.peripherals[p1]
            return (
                f"PINSEL conflict: '{new_peripheral}' and '{p1}' share PINSEL bits "
                f"({existing.pinsel_reg} {existing.pinsel_bits}). "
                f"They cannot be active simultaneously on LPC2148."
            )

    return None   # No conflict


def register_peripheral(
    state: ConversationState,
    peripheral: str,
    owner_task: str,
    vic_channel: Optional[int] = None,
) -> None:
    """
    Register peripheral ownership in a session state.
    Uses the known PINSEL map; falls back to unknown bits if not in map.
    Mutates state in place — caller is responsible for calling update_session().
    """
    meta = _PERIPHERAL_PINSEL_MAP.get(peripheral, {
        "reg": "PINSEL0", "bits": "unknown", "val": 0
    })
    state.peripherals[peripheral] = PeripheralOwnership(
        peripheral=peripheral,
        owner_task=owner_task,
        pinsel_reg=meta["reg"],
        pinsel_bits=meta["bits"],
        pinsel_val=meta["val"],
        vic_channel=vic_channel,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ARCHITECTURE GRAPH UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def build_graph_node(
    name: str,
    node_type: str,
    connections_to: Optional[list] = None,
    **metadata,
) -> ArchitectureNode:
    """Factory for ArchitectureNode with safe defaults."""
    return ArchitectureNode(
        name=name,
        node_type=node_type,
        connections_to=connections_to or [],
        metadata=metadata,
    )


def find_queue_producers(graph: list, queue_name: str) -> list:
    """Return names of all nodes that connect TO the given queue."""
    return [node.name for node in graph
            if queue_name in node.connections_to]


def find_queue_consumers(graph: list, queue_name: str) -> list:
    """Return names of all queue nodes that receive FROM the given queue."""
    # A consumer is a node that has the queue in its connections_to
    # from the queue's perspective, consumers are nodes the queue connects to
    queue_node = next((n for n in graph if n.name == queue_name), None)
    if queue_node:
        return queue_node.connections_to
    return []


def find_peripheral_owner(graph: list, peripheral_name: str) -> Optional[str]:
    """Return the task name that owns the peripheral node, or None."""
    peri_node = next(
        (n for n in graph if n.name == peripheral_name and n.node_type == "peripheral"),
        None
    )
    if peri_node and peri_node.connections_to:
        return peri_node.connections_to[0]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# STATE SNAPSHOT UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def snapshot_state(state: ConversationState) -> ConversationState:
    """
    Create a deep copy of ConversationState for safe rollback.
    Used by modifier.py: snapshot → modify → validate → commit OR rollback.
    """
    import copy
    return copy.deepcopy(state)


def record_turn(
    state: ConversationState,
    query: str,
    modification_type: Optional[str],
    diff_summary: str,
) -> None:
    """
    Append a turn record to state.turn_history.
    Trims to MAX_TURN_HISTORY to bound memory.
    Mutates state in place.
    """
    state.turn_count += 1
    state.turn_history.append({
        "turn":              state.turn_count,
        "query":             query,
        "modification_type": modification_type,
        "diff_summary":      diff_summary,
        "timestamp":         time.time(),
    })
    # Trim oldest entries beyond limit
    if len(state.turn_history) > MAX_TURN_HISTORY:
        state.turn_history = state.turn_history[-MAX_TURN_HISTORY:]
