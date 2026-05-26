import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.parser import parse_query
from app.services.rag import retrieve_context

queries = [
    "What is DLAB and why is it needed?",
    "What is the role of the VIC in interrupt handling?",
    "How do I configure the PLL for 60MHz?"
]

with open("rag_debug_output.txt", "w", encoding="utf-8") as out:
    for query in queries:
        parsed = parse_query(query)
        board = "lpc2148"
        out.write(f"\n{'='*80}\n")
        out.write(f"QUERY: {query}\n")
        context = retrieve_context(parsed, board)
        out.write(f"RETRIEVED CONTEXT (first 2000 chars):\n")
        out.write(context[:2000])
        out.write(f"\n{'='*80}\n")
