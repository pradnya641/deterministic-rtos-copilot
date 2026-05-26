import sys, requests
sys.stdout.reconfigure(encoding='utf-8')
r = requests.post("http://127.0.0.1:8000/ask", json={"text": "explain adc noise behavior"}, timeout=60)
print("STATUS CODE:", r.status_code)
print("RAW JSON:", r.json())
