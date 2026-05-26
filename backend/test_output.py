import requests
import json

url = "http://localhost:8000/ask"
payload = {
    "text": "Setup ADC for channel 1 on P0.28"
}

try:
    response = requests.post(url, json=payload)
    data = response.json()
    with open("test_response.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("Success! Response saved to test_response.json")
except Exception as e:
    print(f"Error: {e}")
