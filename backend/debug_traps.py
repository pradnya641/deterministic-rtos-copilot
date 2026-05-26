import requests

tests = [
    ("TRAP-001", "Why is baud rate important in ADC configuration?"),
    ("TRAP-003", "Can UART FIFO affect ADC conversion accuracy?"),
    ("TRAP-004", "Configure ADCSRA register for ADC in LPC2148"),
    ("TRAP-005", "Use analogRead() to configure ADC on LPC2148"),
]
for tid, q in tests:
    r = requests.post("http://localhost:8000/ask", json={"text": q})
    d = r.json()
    resp = d.get("response", "")[:150]
    print(f"[{tid}] status={d.get('status')} | {repr(resp)}")
