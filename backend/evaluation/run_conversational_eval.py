import os
import json
import time
import argparse
from fastapi.testclient import TestClient
from app.main import app
from app.routes.query import _extract_c_code, _safe_gcc_syntax_check
from app.services.conversation_state import get_or_create_session

client = TestClient(app)

SUITES = [
    "routing",
    "rollback",
    "rtos_safety",
    "polling_conversion",
    "optimization",
    "conversational_memory"
]

def ensure_dirs():
    os.makedirs("evaluation/results", exist_ok=True)
    os.makedirs("evaluation/failures", exist_ok=True)

def load_suite(suite_name):
    path = f"evaluation/suites/{suite_name}.json"
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_evaluation(compare_file=None):
    ensure_dirs()
    print("=" * 60)
    print("STARTING DETERMINISTIC CONVERSATIONAL EVALUATION RUNNER")
    print("=" * 60)

    all_results = {}
    total_turns_run = 0
    passed_compilations = 0
    total_compilations = 0
    rollbacks_triggered = 0

    for suite_name in SUITES:
        suite = load_suite(suite_name)
        if not suite:
            print(f"Suite {suite_name} not found or empty. Skipping.")
            continue

        print(f"\nRunning Suite: {suite_name.upper()}")
        print("-" * 50)
        all_results[suite_name] = []

        for scenario in suite:
            sc_name = scenario.get("name", "unnamed_scenario")
            print(f"Scenario: {sc_name}")
            
            # Persistent session ID for scenario continuity
            session_id = f"eval_{suite_name}_{sc_name}_{int(time.time())}"
            scenario_turns = []
            
            # Track previous state to archive on failure
            previous_committed_state = None

            for turn_idx, query in enumerate(scenario.get("turns", []), 1):
                print(f"  Turn {turn_idx}: '{query}'")
                
                # Fetch state from store *before* the post request to keep the original state
                try:
                    pre_state = get_or_create_session(session_id)
                    previous_committed_state = {
                        "system_name": pre_state.system_name,
                        "generated_code": pre_state.generated_code,
                        "tasks": pre_state.tasks,
                        "queues": pre_state.queues,
                        "isr_topology": pre_state.isr_topology,
                        "peripherals": list(pre_state.peripherals.keys())
                    }
                except Exception:
                    previous_committed_state = None

                start_time = time.time()
                response = client.post("/chat", json={
                    "session_id": session_id,
                    "text": query
                })
                latency_ms = int((time.time() - start_time) * 1000)

                assert response.status_code == 200, f"HTTP Error {response.status_code}"
                res_data = response.json()
                
                status = res_data.get("status")
                response_text = res_data.get("response", "")
                diff = res_data.get("diff", "")
                snapshot = res_data.get("architecture_snapshot")

                # Extract route classification and normalized query
                # Fuzzy normalization can append hints or we can classify from the response
                normalized_query = query
                route_type = "NEW_ARCHITECTURE_REQUEST"
                if "Evolution Diffs" in response_text or "Modification" in response_text or "Rejection" in response_text:
                    route_type = "ARCHITECTURE_MODIFICATION"
                
                # Compilation & Rollback safety analysis
                compile_valid = True
                compiler_err = None
                rollback_triggered = False
                validation_errors = []

                # Compile syntax check if code block was modified
                if "```c" in response_text:
                    c_code = _extract_c_code(response_text)
                    if c_code:
                        total_compilations += 1
                    ok, msg = _safe_gcc_syntax_check(c_code)
                    if not ok:
                        compile_valid = False
                        compiler_err = msg
                        print(f"    [COMPILER FAILURE]: {msg}")
                    else:
                        passed_compilations += 1

                # Rollback detection
                if status == "error":
                    rollback_triggered = True
                    rollbacks_triggered += 1
                    print("    [ROLLBACK TRIGGERED]")
                    # Parse validation errors out of the response text
                    for line in response_text.splitlines():
                        if line.strip().startswith("- "):
                            validation_errors.append(line.strip()[2:])

                turn_log = {
                    "turn": turn_idx,
                    "query": query,
                    "normalized_query": normalized_query,
                    "route_type": route_type,
                    "response": response_text,
                    "diff": diff,
                    "compile_valid": compile_valid,
                    "rollback_triggered": rollback_triggered,
                    "dashboard_snapshot": snapshot,
                    "latency_ms": latency_ms,
                    "validation_errors": validation_errors
                }
                scenario_turns.append(turn_log)
                total_turns_run += 1

                # Save failure artifacts
                if not compile_valid or rollback_triggered or validation_errors:
                    fail_filename = f"evaluation/failures/fail_{suite_name}_{sc_name}_turn{turn_idx}_{int(time.time())}.json"
                    with open(fail_filename, "w", encoding="utf-8") as ff:
                        json.dump({
                            "mutation_request": query,
                            "architecture_diff": diff,
                            "broken_code": response_text,
                            "canonical_extracted_code": c_code,
                            "compiler_stderr": compiler_err,
                            "dashboard_snapshot": snapshot,
                            "previous_committed_state": previous_committed_state
                        }, ff, indent=2)
                    print(f"    [ARTIFACT SAVED] Saved failure artifacts to {fail_filename}")

            all_results[suite_name].append({
                "scenario_name": sc_name,
                "turns": scenario_turns
            })

    # Save complete evaluation logs
    log_path = "evaluation/results/eval_log.json"
    with open(log_path, "w", encoding="utf-8") as lf:
        json.dump(all_results, lf, indent=2)
    print(f"\nEvaluation Log saved to {log_path}")

    # Generate Markdown, HTML and DOCX Reports
    from evaluation.reporter import generate_reports
    generate_reports(all_results, compare_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", help="Path to previous eval_log.json for before/after comparison", default=None)
    args = parser.parse_args()
    
    run_evaluation(args.compare)
