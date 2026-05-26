import requests
import json

url = "http://127.0.0.1:8000/ask"
payload = {
    "text": "How do I configure pin P0.1 as an output for an LED?"
}

print(f"Sending POST request to {url}...")
try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Request failed: {e}")
