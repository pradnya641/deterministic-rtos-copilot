import requests
try:
    resp = requests.get("http://localhost:11434/api/tags")
    print(f"Status: {resp.status_code}")
    print(f"Models: {[m['name'] for m in resp.json().get('models', [])]}")
except Exception as e:
    print(f"Error: {e}")
