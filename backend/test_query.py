import requests

url = "http://localhost:8000/ask"
payload = {
    "text": "Setup ADC for channel 1 on P0.28"
}

response = requests.post(url, json=payload)
print(response.json())
