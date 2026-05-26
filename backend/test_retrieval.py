import sys
import os

# Add the backend path so we can import app modules
sys.path.append(os.path.abspath("c:\\genai_project\\backend"))

from app.services.rag import retrieve_context

parsed = {
    "raw": "How do I configure PWM on LPC2148?",
    "pins": [],
    "components": ["PWM"],
    "intent": "configure"
}

context = retrieve_context(parsed, "lpc2148")

print("--- RETRIEVED CONTEXT ---")
print(context)
print("-------------------------")
