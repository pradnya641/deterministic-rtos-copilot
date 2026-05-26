"""
Structured JSON response schema for the Embedded Systems Gen-AI API.

All responses are now structured with:
  - intent classification
  - domain
  - source attribution
  - explainability trace
  - content (reasoning / code / architecture)
  - metadata (latency, confidence, version)

This replaces raw text responses and enables frontend rendering
of structured engineering outputs.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import time


API_VERSION = "2.0.0"


@dataclass
class RTOSInfo:
    """Populated for rtos_architecture intent."""
    tasks:      List[Dict] = field(default_factory=list)
    queues:     List[Dict] = field(default_factory=list)
    semaphores: List[str]  = field(default_factory=list)
    isr_notes:  List[str]  = field(default_factory=list)


@dataclass
class HardwareInfo:
    """Populated for hardware_reasoning intent."""
    registers:    List[str] = field(default_factory=list)
    peripherals:  List[str] = field(default_factory=list)
    timing_notes: List[str] = field(default_factory=list)


@dataclass
class StructuredResponse:
    # ── Core classification ────────────────────────────────────────────
    intent:      str
    domain:      str                      # hardware / rtos / sensor / protocol / system

    # ── Content ───────────────────────────────────────────────────────
    answer:      str                      # primary human-readable response
    code:        Optional[str]  = None    # C code if peripheral_configuration
    reasoning:   Optional[str]  = None    # hardware reasoning chain if applicable
    architecture: Optional[Dict] = None   # full blueprint if system_architecture

    # ── Structured metadata ────────────────────────────────────────────
    modules:     List[str]      = field(default_factory=list)   # detected peripherals
    sensors:     List[str]      = field(default_factory=list)   # detected sensors
    rtos_info:   Optional[RTOSInfo]    = None
    hw_info:     Optional[HardwareInfo] = None

    # ── Explainability ─────────────────────────────────────────────────
    explainability: Dict[str, str] = field(default_factory=dict)
    source:         str            = "Hardware Deterministic Engine"
    confidence:     str            = "HIGH"     # HIGH / MEDIUM / LOW / REJECTED

    # ── System metadata ────────────────────────────────────────────────
    version:     str  = API_VERSION
    latency_ms:  int  = 0
    timestamp:   str  = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


def build_response(
    intent:    str,
    answer:    str,
    parsed:    dict,
    *,
    code:         str | None  = None,
    reasoning:    str | None  = None,
    architecture: dict | None = None,
    explainability: dict | None = None,
    source:    str = "Hardware Deterministic Engine",
    confidence: str = "HIGH",
    latency_ms: int = 0,
) -> StructuredResponse:
    """
    Factory function to build a fully structured response.
    Called by the route handler after generate_answer() returns.
    """

    # Determine domain from intent
    domain_map = {
        "hardware_reasoning":       "hardware",
        "peripheral_configuration": "hardware",
        "embedded_debugging":       "hardware",
        "rtos_architecture":        "rtos",
        "sensor_integration":       "sensors",
        "communication_design":     "protocols",
        "automotive_logic":         "automotive",
        "system_architecture":      "system",
        "system":                   "meta",
        "unknown":                  "unknown",
    }
    domain = domain_map.get(intent, "hardware")

    # Extract hardware info if applicable
    hw_info = None
    if intent in ("hardware_reasoning", "peripheral_configuration", "embedded_debugging"):
        hw_info = HardwareInfo(
            peripherals=parsed.get("peripherals", []),
        )

    # Extract RTOS info if applicable
    rtos_info = None
    if intent == "rtos_architecture":
        rtos_info = RTOSInfo()

    return StructuredResponse(
        intent=intent,
        domain=domain,
        answer=answer,
        code=code,
        reasoning=reasoning,
        architecture=architecture,
        modules=parsed.get("peripherals", []),
        sensors=parsed.get("sensors", []),
        hw_info=hw_info,
        rtos_info=rtos_info,
        explainability=explainability or {},
        source=source,
        confidence=confidence,
        latency_ms=latency_ms,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        version=API_VERSION,
    )
