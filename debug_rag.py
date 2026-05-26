import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.parser import parse_query
from app.services.rag import retrieve_context

query = "What is DLAB and why is it needed?"
parsed = parse_query(query)
board = "lpc2148"

print(f"--- DEBUG RAG for: {query} ---")
context = retrieve_context(parsed, board)
print(f"Context Length: {len(context)}")
print("--- CONTEXT START ---")
print(context[:2000])
print("--- CONTEXT END ---")
