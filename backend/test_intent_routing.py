from app.services.parser import parse_query
from app.services.llm import generate_answer

def test_pin_mapping_routing():
    query = "Pin mapping for PWM5"
    parsed = parse_query(query)
    print(f"Parsed Intent: {parsed['intent']}")
    print(f"Parsed Channels: {parsed.get('channels', [])}")
    print(f"Parsed Peripherals: {parsed['peripherals']}")
    
    # Simulate a generic context
    context = "PWM5 is on P0.21. PINSEL1 bits [11:10] = 01."
    
    response = generate_answer(parsed, context, "lpc2148")
    
    try:
        print("\n--- Response ---")
        # Use utf-8 for terminal printing to avoid emoji errors on Windows
        print(response.encode('utf-8').decode('ascii', 'ignore'))
    except Exception:
        print("\n[Response received but contained non-ascii characters]")
    
    if "Pin Mapping" in response and "P0.21" in response:
        print("\n[SUCCESS]: Routed to Pin Mapping Gold Data.")
    else:
        print("\n[FAILURE]: Generic response or code template returned.")

if __name__ == "__main__":
    test_pin_mapping_routing()
