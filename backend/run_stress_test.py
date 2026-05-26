import requests
import time

QUESTIONS = [
    # LEVEL 1 — Precision Traps
    "What happens if ADC result is read before DONE = 1?",
    "What happens if ADC START bits are never set?",
    "What happens if ADC PDN = 0?",
    "What happens if PWMMR1 > PWMMR0?",
    "What happens if UART DLAB is not cleared?",

    # LEVEL 2 — Collision Tests
    "Explain ADC DONE bit",
    "Explain ADC START bit",
    "Explain difference between DONE and START",

    # LEVEL 3 — Deep Reasoning
    "Why do ADC readings fluctuate even for constant input?",
    "How does input impedance affect ADC accuracy?",
    "Why must ADC clock be <= 4.5 MHz?",

    # LEVEL 4 — Invalid Queries
    "What is baud rate of ADC?",
    "How does PWM duty cycle control ADC sampling?",
    "Can UART FIFO improve ADC accuracy?",

    # LEVEL 5 — Cross-Domain Isolation
    "Configure ADC and explain UART DLAB",
    "Explain PWM and ADC noise together",

    # LEVEL 6 — Edge Conditions
    "What happens if ADC clock is too LOW?",
    "What happens if ADC input is floating?",
    "What happens if PWM output is not enabled in PWMPCR?",

    # LEVEL 7 — Ambiguity Handling
    "Explain ADC",

    # LEVEL 8 — System Integrity
    "Explain difference between ADC and UART",
    "Why should AI not hallucinate hardware registers?",
    "What is RAG in your system?"
]

URL = "http://localhost:8000/ask"
OUTPUT_FILE = "final_evaluation_results.txt"

def run_tests():
    print(f"Starting Final Evaluation ({len(QUESTIONS)} questions)...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=== GEN-AI SYSTEM FINAL EVALUATION ===\n\n")
        
        for i, q in enumerate(QUESTIONS, 1):
            print(f"Testing Q{i}: {q}")
            f.write(f"QUESTION {i}: {q}\n")
            f.write("-" * 50 + "\n")
            
            start_time = time.time()
            try:
                response = requests.post(URL, json={"text": q}, timeout=120)
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    answer = data.get("response", "No answer field found.")
                    
                    f.write(f"STATUS: {status}\n")
                    f.write(f"TIME: {elapsed:.2f}s\n\n")
                    f.write(f"ANSWER:\n{answer}\n\n")
                else:
                    f.write(f"STATUS: error\n")
                    f.write(f"TIME: {elapsed:.2f}s\n\n")
                    f.write(f"Error HTTP {response.status_code}\n\n")
            
            except Exception as e:
                f.write(f"STATUS: failed\n")
                f.write(f"Error: {str(e)}\n\n")
            
            f.write("=" * 80 + "\n\n")
            
    print(f"Test complete! Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_tests()
