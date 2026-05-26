import re
import requests
import time

# Extract questions
questions = []
with open("10_10_stress_test_results.txt", "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("QUESTION "):
            m = re.match(r"QUESTION \d+: (.*)", line.strip())
            if m:
                questions.append(m.group(1))

URL = "http://localhost:8000/ask"
OUTPUT_FILE = "final_36_questions_results.txt"

def run_tests():
    print(f"Starting Final Evaluation ({len(questions)} questions)...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=== GEN-AI SYSTEM FINAL EVALUATION (36 QUESTIONS) ===\n\n")
        
        for i, q in enumerate(questions, 1):
            print(f"Testing Q{i}: {q}")
            f.write(f"QUESTION {i}: {q}\n")
            f.write("-" * 50 + "\n")
            
            start_time = time.time()
            try:
                response = requests.post(URL, json={"text": q}, timeout=120)
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    answer = data.get("response", "No answer field found.")
                    
                    f.write(f"STATUS: {status}\n")
                    f.write(f"TIME: {elapsed:.2f}s\n\n")
                    f.write(f"ANSWER:\n{answer}\n\n")
                else:
                    f.write(f"STATUS: error\n")
                    f.write(f"TIME: {elapsed:.2f}s\n\n")
                    f.write(f"Error HTTP {response.status_code}\n\n")
            
            except Exception as e:
                f.write(f"STATUS: failed\n")
                f.write(f"Error: {str(e)}\n\n")
            
            f.write("=" * 80 + "\n\n")
            f.flush()
            
    print(f"Test complete! Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_tests()
