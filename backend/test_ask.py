import requests
import json

URL = "http://localhost:8000/chat"
payload = {"session_id": "test_session_manual", "text": "Generate UART ISR pipeline"}
r = requests.post(URL, json=payload)
print(f"Status: {r.status_code}")
try:
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(r.text)
