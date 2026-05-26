import re
from typing import List

# ─────────────────────────────────────────────────────────
# Intent keyword groups – kept for clarity and re‑use
INTENT_KEYWORDS = {
    "rtos_architecture": [
        "freertos", "rtos", "task", "scheduler", "semaphore", "mutex",
        "queue", "vtaskcreate", "priority", "preempt", "tick", "isr",
        "taskdelay", "vtaskdelay", "xtask", "xqueue", "interrupt handler",
    ],
    "peripheral_configuration": [
        "configure", "initialize", "setup", "init", "write code", "generate code",
    ],
    "sensor_integration": [
        "hc-sr04", "ultrasonic", "lm35", "temperature", "mpu6050", "gyroscope",
        "accelerometer", "gps", "nmea", "sensor", "trigger", "echo", "trig",
        "distance", "altitude",
    ],
    "communication_design": [
        "can bus", "can frame", "spi", "i2c", "frame structure", "baud rate",
        "synchronization", "protocol", "miso", "mosi", "sclk", "cs", "scl", "sda",
        "arbitration", "ack", "nack",
    ],
    "automotive_logic": [
        "adas", "automotive", "bcm", "telematics", "lidar", "radar", "camera",
        "fusion", "lane", "collision", "ecu", "dbc", "fault handling",
        "safety", "actuator", "vehicle",
    ],
    "embedded_debugging": [
        "debug", "fault", "hardfault", "stack overflow", "wrong output",
        "not working", "register incorrect", "value incorrect", "watchdog",
        "hang", "stuck", "timeout", "corruption",
    ],
    "system_architecture": [
        "architecture", "design", "system", "blueprint", "workflow",
        "pipeline", "block diagram", "overview", "structure",
    ],
    "system": ["hallucination", "routing", "knowledge base", "deterministic", "llm", "rag"],
    "hardware_reasoning": [
        "why", "how", "what", "does", "indicate", "function", "happens",
        "behavior", "effect", "purpose", "role", "resolution", "calculate",
        "reduce", "explain", "difference", "impact", "pin mapping", "pinout", "pins",
    ],
}

def detect_intent(query: str) -> str:
    q = query.lower()

    # 1. RTOS must be FIRST — before peripheral_configuration
    if any(k in q for k in ["freertos", "rtos", "task", "scheduler",
                              "semaphore", "mutex", "queue", "vtaskdelay",
                              "xtask", "xqueue", "interrupt handler",
                              "priority", "preempt", "tick"]):
        return "rtos_architecture"

    # 2. Sensor integration — but NOT echo/distance alone
    if any(k in q for k in ["hc-sr04", "lm35", "mpu6050", "gps", "sensor",
                              "ultrasonic", "temperature", "accelerometer",
                              "gyroscope", "nmea"]):
        return "sensor_integration"
    if ("echo" in q or "distance" in q) and any(
            k in q for k in ["hc-sr04", "ultrasonic", "trig"]):
        return "sensor_integration"

    # 3. Communication design
    if any(k in q for k in ["can bus", "can frame", "spi", "i2c",
                              "baud rate", "protocol", "miso", "mosi",
                              "sclk", "cs", "scl", "sda", "arbitration"]):
        return "communication_design"

    # 4. Automotive
    if any(k in q for k in ["adas", "automotive", "bcm", "telematics",
                              "lidar", "radar", "collision", "ecu",
                              "fault handling", "vehicle"]):
        return "automotive_logic"

    # 5. Embedded debugging
    if any(k in q for k in ["debug", "fault", "hardfault", "stack overflow",
                              "not working", "wrong output", "watchdog",
                              "hang", "stuck", "timeout"]):
        return "embedded_debugging"

    # 6. Peripheral configuration — AFTER rtos check
    if any(k in q for k in ["configure", "initialize", "setup", "init",
                              "write code", "generate code"]):
        return "peripheral_configuration"

    # 7. System architecture — narrow keywords only
    if any(k in q for k in ["architecture", "blueprint", "block diagram",
                              "full design", "complete design"]):
        return "system_architecture"

    # 8. System meta
    if any(k in q for k in ["hallucination", "routing", "knowledge base",
                              "deterministic", "llm"]):
        return "system"

    # 9. Hardware reasoning — catch-all for explanation/theory queries
    if any(k in q for k in ["why", "how", "what", "does", "explain",
                              "difference", "purpose", "role", "resolution",
                              "calculate", "effect", "behavior", "impact"]):
        return "hardware_reasoning"

    # 10. Cross-peripheral queries default to hardware_reasoning
    peripheral_count = sum([
        any(k in q for k in ["adc", "analog"]),
        any(k in q for k in ["pwm", "waveform"]),
        any(k in q for k in ["uart", "serial"]),
        any(k in q for k in ["spi", "i2c", "can"]),
    ])
    if peripheral_count > 1:
        return "hardware_reasoning"

    return "unknown"

def get_secondary_intents(query: str, primary_intent: str) -> List[str]:
    """Return any additional intents detected in the query, excluding the primary.
    Supports composite queries like "Configure UART and schedule a FreeRTOS task".
    """
    q = query.lower()
    secondary = []
    for intent, keywords in INTENT_KEYWORDS.items():
        if intent == primary_intent or intent == "unknown":
            continue
        if any(k in q for k in keywords):
            secondary.append(intent)
    return secondary

def classify_route_type(query: str) -> str:
    q = query.lower().strip()
    
    # Check for explicit new architecture generation verbs
    new_verbs = ["generate", "create", "build", "design", "synthesis", "synthesize", "fresh"]
    
    # Check if any new verb is present as a word boundary
    has_new_verb = any(re.search(rf"\b{v}\b", q) for v in new_verbs)
    
    # Check if the query explicitly references the current/existing state
    references_state = any(k in q for k in [
        "current", "existing", "active", "previous", "prior", "state", 
        "this system", "this architecture", "modify", "change", "add to", 
        "update", "remove from", "convert", "replace"
    ])
    
    if has_new_verb and not references_state:
        return "NEW_ARCHITECTURE_REQUEST"
        
    # Check if it has modification keywords
    from app.services.normalizer import is_modification_query
    if is_modification_query(q):
        return "ARCHITECTURE_MODIFICATION"
        
    return "NEW_ARCHITECTURE_REQUEST"

def parse_query(query: str) -> dict:
    """
    Production‑grade parser for the Embedded Systems Gen‑AI assistant.
    Detects intent, peripherals, sensors, protocols, and parameters.
    """
    intent = detect_intent(query)
    secondary_intents = get_secondary_intents(query, intent)
    q = query.lower()

    # ── Peripheral Extraction ──
    found_peripherals = []
    if "adc" in q or "analog" in q:
        found_peripherals.append("ADC")
    if "uart" in q or "serial" in q:
        found_peripherals.append("UART")
    if "pwm" in q or "waveform" in q:
        found_peripherals.append("PWM")
    if "spi" in q:
        found_peripherals.append("SPI")
    if "i2c" in q:
        found_peripherals.append("I2C")
    if "can" in q and "can bus" in q:
        found_peripherals.append("CAN")
    if "gpio" in q or "p0." in q or ("pin" in q and not any(x in q for x in ["adc", "uart", "pwm", "spi", "i2c"])):
        found_peripherals.append("GPIO")

    # ── Sensor Extraction ──
    found_sensors = []
    if "hc-sr04" in q or "ultrasonic" in q:
        found_sensors.append("HC‑SR04")
    if "lm35" in q or "temperature" in q:
        found_sensors.append("LM35")
    if "mpu6050" in q or "gyroscope" in q or "accelerometer" in q:
        found_sensors.append("MPU6050")
    if "gps" in q or "nmea" in q:
        found_sensors.append("GPS")

    # ── Parameter Extraction ──
    params = {"baud": 9600, "duty": 50, "channel": 1, "priority": 1, "stack": 512}
    numbers = re.findall(r"\d+", query)
    for num in numbers:
        val = int(num)
        if val in [9600, 115200, 19200, 38400, 57600]:
            params["baud"] = val
        elif 0 < val <= 100 and "%" in query:
            params["duty"] = val
        elif val < 8 and ("channel" in q or "ad0." in q):
            params["channel"] = val

    # Queue depth parsing
    if any(k in q for k in ["queue", "q depth", "depth", "q"]):
        for num in numbers:
            val = int(num)
            if val > 0 and val not in [9600, 115200, 19200, 38400, 57600] and "%" not in query:
                params["target_depth"] = val
                break

    # Priority parsing
    if "priority" in q or "prio" in q:
        for num in numbers:
            val = int(num)
            if 0 < val < 32:
                params["priority"] = val
                break

    # Stack parsing
    if "stack" in q or "stk" in q:
        for num in numbers:
            val = int(num)
            if val >= 64 and val not in [9600, 115200, 19200, 38400, 57600]:
                params["stack"] = val
                break

    return {
        "intent": intent,
        "secondary_intents": secondary_intents,
        "secondary_intent": (
            "hardware_reasoning"
            if any(k in query.lower() for k in
                   ["why", "explain", "reason", "because", "how does"])
            else None
        ),
        "peripherals": found_peripherals,
        "sensors": found_sensors,
        "components": found_peripherals,   # backward compat
        "params": params,
        "raw_query": query,
        "board": "LPC2148",
        "route_type": classify_route_type(query),
    }
