import requests
import json
import time
from datetime import datetime

URL = "http://localhost:8000/ask"
OUTPUT_FILE = "final_stress_test_results.txt"

CATEGORIES = {
    "CATEGORY 1 — CROSS-DOMAIN TRAPS": [
        "Why is baud rate important in ADC configuration?",
        "Can PWM duty cycle control ADC sampling frequency?",
        "Can UART FIFO improve ADC conversion accuracy?",
        "Configure ADCSRA register for LPC2148 ADC.",
        "Use analogRead() to configure ADC on LPC2148.",
        "Can CAN bus improve ADC voltage resolution?"
    ],
    "CATEGORY 2 — HARDWARE REASONING": [
        "What happens if ADC result is read before DONE = 1?",
        "Why must ADC clock remain below 4.5 MHz?",
        "Explain ADC quantization error.",
        "What happens if PWMMR1 > PWMMR0?",
        "What happens if UART DLAB is not cleared?",
        "Why are analog and digital grounds separated?",
        "Explain ADC sample-and-hold behavior."
    ],
    "CATEGORY 3 — RTOS SAFETY": [
        "Can mutexes be used inside ISR?",
        "Why is printf dangerous inside interrupts?",
        "When should queues be preferred over semaphores?",
        "Explain priority inversion in FreeRTOS.",
        "Why should ISRs remain short in RTOS systems?"
    ],
    "CATEGORY 4 — MULTI-INTENT TESTS": [
        "Configure ADC on channel 1 and explain ADC noise behavior.",
        "Generate UART0 initialization code and explain DLAB logic.",
        "Create FreeRTOS architecture for ultrasonic obstacle detection and explain queue usage.",
        "Configure PWM and explain duty cycle behavior."
    ],
    "CATEGORY 5 — ARCHITECTURE GENERATION": [
        "Design ADAS obstacle detection system using LPC2148 and FreeRTOS.",
        "Design smart parking system using ultrasonic sensors and RTOS.",
        "Design telematics tracking system using GPS and FreeRTOS.",
        "Generate RTOS architecture for sensor fusion using MPU6050 and ultrasonic sensor."
    ],
    "CATEGORY 6 — SENSOR VALIDATION": [
        "Can MPU6050 connect directly to 5V LPC2148 I2C lines?",
        "Why does HC-SR04 require pulse timing measurement?",
        "Why is filtering important for LM35 readings?",
        "Explain calibration requirements for MPU6050."
    ],
    "CATEGORY 7 — EXPLAINABILITY TESTS": [
        "Why did you choose queue instead of semaphore?",
        "Why is sensor acquisition task given higher priority?",
        "Why should ADC sampling be periodic instead of event-driven?",
        "Why is interrupt-driven UART preferred over polling?"
    ],
    "CATEGORY 10 — DETERMINISTIC CONSISTENCY": [
        "Explain ADC noise behavior.",
        "Explain ADC noise behavior.",
        "Explain ADC noise behavior."
    ]
}

def run_stress_test():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"FINAL STRESS TEST REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

        for category, questions in CATEGORIES.items():
            f.write(f"### {category}\n")
            f.write("-" * len(category) + "\n\n")
            
            for i, q in enumerate(questions, 1):
                print(f"Testing [{category}] Q{i}: {q[:50]}...")
                t0 = time.time()
                try:
                    r = requests.post(URL, json={"text": q}, timeout=30)
                    latency = time.time() - t0
                    
                    if r.status_code == 200:
                        data = r.json()
                        f.write(f"Q: {q}\n")
                        f.write(f"Intent: {data.get('intent', 'N/A')}\n")
                        f.write(f"Status: {data.get('status', 'N/A')}\n")
                        f.write(f"Latency: {latency:.2f}s\n")
                        f.write(f"Response:\n{data.get('response', '')}\n")
                        
                        # Verify JSON structure
                        missing = [k for k in ["status", "intent", "response", "metadata"] if k not in data]
                        if missing:
                            f.write(f"[JSON ERROR] Missing fields: {missing}\n")
                    else:
                        f.write(f"Q: {q}\n")
                        f.write(f"HTTP ERROR: {r.status_code}\n")
                except Exception as e:
                    f.write(f"Q: {q}\n")
                    f.write(f"EXCEPTION: {str(e)}\n")
                
                f.write("\n" + "."*40 + "\n\n")
            f.write("\n")

    print(f"Stress test complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_stress_test()
