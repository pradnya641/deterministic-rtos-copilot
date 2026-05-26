import requests
import json
import time

URL = "http://127.0.0.1:8000/ask"
print("Benchmark script started")
print(f"Target URL: {URL}")

TEST_CASES = {
    "LEVEL 1: Basic Functionality": [
        "Configure ADC on channel AD0.2 (P0.29)",
        "Configure PWM1 with 25% duty cycle",
        "Initialize UART0 for 115200 baud",
        "Configure GPIO P0.10 as output",
        "Read ADC value from AD0.1 continuously"
    ],
    "LEVEL 2: Register Understanding": [
        "What is the role of AD0CR in LPC2148?",
        "Why must ADC clock be <= 4.5 MHz?",
        "Difference between AD0DR and AD0GDR?",
        "What happens if PDN bit is 0?",
        "Explain CLKDIV calculation for ADC"
    ],
    "LEVEL 3: Edge Cases": [
        "What happens if PWMMR0 = 0?",
        "What if START bits are not cleared before ADC conversion?",
        "What happens if PINSEL is not configured?",
        "What if UART DLAB is not cleared?",
        "What if ADC DONE bit is ignored?"
    ],
    "LEVEL 4: Trap Questions": [
        "Configure ADC using register AD1CR",
        "Use Arduino PWM registers for LPC2148",
        "What is TCCR2A in LPC2148?",
        "Configure SPI using register SPCR"
    ],
    "LEVEL 5: Multi-Step Engineering Queries": [
        "Configure ADC + UART to send ADC values serially",
        "Generate PWM signal based on ADC input",
        "Configure interrupt-driven ADC conversion",
        "Read multiple ADC channels sequentially",
        "Build a simple sensor monitoring system using LPC2148"
    ],
    "LEVEL 6: Retrieval Stress Test": [
        "Pin mapping for PWM5",
        "Address of PWMPCR register",
        "Bit position of AD0CR PDN",
        "UART0 register memory map",
        "Full register table for ADC"
    ],
    "BONUS: One-Shot Validation": [
        "Configure ADC but do NOT include pin mapping",
        "Give only register explanation, no code",
        "If information is missing, explicitly say so"
    ]
}

def run_tests():
    filename = "redemption_results.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Hardware RAG Assistant Benchmark Results\n")
        f.write(f"Generated on: {time.ctime()}\n\n")
        f.flush()
        
    for level, queries in TEST_CASES.items():
        print(f"Running {level}...")
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"## {level}\n" + "="*len(level) + "\n\n")
            f.flush()
            
            for query in queries:
                print(f"  Query: {query}")
                try:
                    start_time = time.time()
                    # Increased timeout to 120s for slow LLM responses
                    resp = requests.post(URL, json={"text": query}, timeout=120)
                    elapsed = time.time() - start_time
                    
                    data = resp.json()
                    f.write(f"### Query: {query}\n")
                    f.write(f"**Status:** {data.get('status')}\n")
                    f.write(f"**Time:** {elapsed:.2f}s\n\n")
                    f.write(f"**Response:**\n{data.get('response')}\n\n")
                    f.write("-" * 40 + "\n\n")
                    f.flush()
                except Exception as e:
                    f.write(f"### Query: {query}\n")
                    f.write(f"**Error:** {str(e)}\n\n")
                    f.write("-" * 40 + "\n\n")
                    f.flush()
                    print(f"    Error: {e}")
            f.write("\n")
            f.flush()

if __name__ == "__main__":
    run_tests()
    print("\nBenchmark complete. Results saved to benchmark_results.txt")
