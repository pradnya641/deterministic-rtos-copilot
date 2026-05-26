def detect_board(parsed: dict) -> str:
    """
    Detects the target hardware board.
    Priority: explicit pins → keyword in raw text → unknown.
    """
    raw = parsed.get("raw_query", "").lower()

    # 1. Check explicit pin names
    if parsed.get("pins"):
        first_pin = parsed["pins"][0]
        if first_pin.startswith("P"):
            return "lpc2148"
        elif first_pin.startswith("GPIO"):
            return "rpi"

    # 2. Keyword detection from raw query
    if "lpc2148" in raw or "lpc214" in raw or "lpc21" in raw:
        return "lpc2148"
    if "raspberry" in raw or "rpi" in raw:
        return "rpi"

    # 3. Default to lpc2148 for common embedded terms (project context)
    embedded_keywords = ["pwm", "pinsel", "timer", "uart", "i2c", "spi", "adc", "gpio"]
    if any(kw in raw for kw in embedded_keywords):
        return "lpc2148"

    return "unknown"
