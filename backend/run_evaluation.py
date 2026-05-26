"""
Deterministic Embedded AI Engine — Evaluation Script
Fires all test queries and prints results for the evaluation report.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/ask"

def query(text, timeout=20):
    try:
        r = requests.post(BASE_URL, json={"text": text}, timeout=timeout)
        d = r.json()
        return {
            "intent":     d.get("intent", "N/A"),
            "confidence": d.get("metadata", {}).get("confidence", "N/A"),
            "response":   d.get("response", str(d))[:600],
            "status":     d.get("status", "N/A"),
        }
    except Exception as e:
        return {"intent": "ERROR", "confidence": "N/A", "response": str(e), "status": "error"}

TESTS = {
    "Peripheral Configuration": [
        "Configure ADC channel 1 on LPC2148.",
        "Initialize UART0 for 9600 baud.",
        "Configure PWM1 for 50% duty cycle.",
        "Configure SPI communication on LPC2148.",
        "Configure I2C at 100kHz.",
    ],
    "Hardware Reasoning": [
        "Explain ADC noise behavior.",
        "Why must ADC clock remain below 4.5 MHz?",
        "What happens if PWMMR0 = 0?",
        "What happens if PWMMR1 > PWMMR0?",
        "Explain UART DLAB behavior.",
    ],
    "RTOS Reasoning": [
        "Why should ISRs remain short in RTOS systems?",
        "What is the difference between queues and semaphores in FreeRTOS?",
        "Why are high-priority tasks dangerous?",
        "Explain priority inversion in RTOS.",
        "Why should ISR avoid blocking APIs in FreeRTOS?",
    ],
    "Sensor Reasoning": [
        "Why does HC-SR04 require pulse timing?",
        "Explain MPU6050 calibration.",
        "Why does sensor drift occur?",
        "Why should sensor tasks have higher priority in RTOS?",
        "Explain oversampling in ADC systems.",
    ],
    "Architecture Synthesis": [
        "Design an RTOS obstacle detection system.",
        "Generate telematics architecture using GPS and GSM.",
        "Build sensor fusion architecture using MPU6050 and GPS.",
        "Design queue-based UART communication system.",
        "Generate FreeRTOS architecture for autonomous robot.",
    ],
    "Trap / Hallucination Tests": [
        "Configure ADCSRA register on LPC2148.",
        "Use analogRead() on LPC2148.",
        "Can ADC baud rate affect PWM timing?",
        "Can PWM duty cycle control ADC sampling frequency?",
        "Configure AVR timer registers on LPC2148.",
    ],
}

results = {}
for category, queries in TESTS.items():
    results[category] = []
    print(f"\n{'='*60}")
    print(f"CATEGORY: {category}")
    print('='*60)
    for q_text in queries:
        print(f"\nQ: {q_text}")
        res = query(q_text)
        print(f"  Intent:     {res['intent']}")
        print(f"  Confidence: {res['confidence']}")
        print(f"  Status:     {res['status']}")
        print(f"  Response:   {res['response'][:300]}")
        results[category].append({"query": q_text, **res})
        time.sleep(0.5)

# Save full results
with open("eval_report_raw.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\n\n✅ Evaluation complete. Results saved to eval_report_raw.json")
