import sys, requests
sys.stdout.reconfigure(encoding='utf-8')

tests = [
    ("explain adc noise behavior",      "noise"),
    ("configure adc on channel 1",      "ADC_Init"),
    ("what happens if PWMMR0 = 0",      "Timer Counter"),
    ("what if UART DLAB is not cleared","DLAB"),
    ("initialize uart0 for 9600 baud",  "UART0_Init"),
]

print("ROUTING VALIDATION")
print("=" * 60)
for query, expected_kw in tests:
    r = requests.post("http://127.0.0.1:8000/ask", json={"text": query}, timeout=60)
    ans = r.json().get("response", r.json().get("answer", ""))
    hit = expected_kw.lower() in ans.lower()
    # Detect cross-domain leak: baud/duty in an adc noise query
    leak = ("baud: 9600" in ans.lower() or "duty: 50" in ans.lower()) and "noise" in query.lower()
    status = "PASS" if (hit and not leak) else "FAIL"
    print(f"[{status}] {query[:48]:<48}  expect={expected_kw}")
    if not hit or leak:
        print(f"       GOT: {ans[:150].strip()}")
