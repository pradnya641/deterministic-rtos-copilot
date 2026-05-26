import json
import os
import sys
import time
import requests
from datetime import datetime

URL = "http://localhost:8000/chat"
BENCH_FILE = r"c:\genai_project\backend\benchmarks\conversational.json"

def run_conversational_tests():
    if not os.path.exists(BENCH_FILE):
        print(f"Benchmark file not found: {BENCH_FILE}")
        return

    with open(BENCH_FILE, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    print(f"\nConversational Copilot Benchmark Suite")
    print(f"Target URL: {URL}")
    print(f"Found {len(scenarios)} scenarios.\n")

    all_results = []
    total_turns = 0
    passed_turns = 0

    for scenario in scenarios:
        sid = scenario["id"]
        desc = scenario["description"]
        print(f"=== Running {sid}: {desc} ===")
        
        # Unique session id for this run
        session_id = f"session_{sid}_{int(time.time())}"
        
        scenario_passed = True
        turns_results = []

        for turn_idx, turn in enumerate(scenario["turns"], 1):
            query = turn["query"]
            expected_mod = turn.get("expected_modification_type")
            expected_kws = turn.get("expected_keywords", [])
            expected_diff_contains = turn.get("expected_diff_contains", [])
            must_not_contain = turn.get("must_not_contain", [])
            arch_preserved = turn.get("architecture_preserved", [])
            
            print(f"  [Turn {turn_idx}] Query: \"{query}\"")
            total_turns += 1
            
            t0 = time.time()
            try:
                payload = {"session_id": session_id, "text": query}
                r = requests.post(URL, json=payload, timeout=30)
                latency = time.time() - t0
                
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status", "unknown")
                    response = data.get("response", "")
                    diff = data.get("diff")
                    snapshot = data.get("architecture_snapshot")
                    turn_num = data.get("turn", 0)
                else:
                    status = f"HTTP_{r.status_code}"
                    response = r.text
                    diff = None
                    snapshot = None
                    turn_num = 0
            except Exception as e:
                latency = time.time() - t0
                status = "error"
                response = f"Exception: {str(e)}"
                diff = None
                snapshot = None
                turn_num = 0

            # Score this turn
            turn_passed = True
            issues = []

            # 1. Check HTTP status / JSON status
            if status not in ("success", "degraded"):
                # If expected_mod is a REJECTED one, status being "error" is correct behavior
                if expected_mod and expected_mod.startswith("REJECTED:"):
                    # This is expected rejection, so this is a PASS
                    pass
                elif "Invalid" in response or "Rejected" in response or "conflict" in response.lower() or "conflict" in status:
                    # Expected validation/conflict rejection
                    pass
                else:
                    turn_passed = False
                    issues.append(f"Response status is '{status}' (expected success or degraded).")

            # 2. Check keywords in primary response
            hits = [kw for kw in expected_kws if kw.lower() in response.lower()]
            if len(hits) < len(expected_kws):
                missing = [kw for kw in expected_kws if kw.lower() not in response.lower()]
                turn_passed = False
                issues.append(f"Missing expected keywords: {missing}")

            # 3. Check forbidden words
            bad_hits = [bad for bad in must_not_contain if bad.lower() in response.lower()]
            if bad_hits:
                turn_passed = False
                issues.append(f"Detected forbidden content: {bad_hits}")

            # 4. Check expected diff contains
            if expected_diff_contains and diff:
                diff_str = json.dumps(diff)
                diff_hits = [dc for dc in expected_diff_contains if dc.lower() in diff_str.lower()]
                if len(diff_hits) < len(expected_diff_contains):
                    missing_diff = [dc for dc in expected_diff_contains if dc.lower() not in diff_str.lower()]
                    turn_passed = False
                    issues.append(f"Missing expected diff elements: {missing_diff}")
            elif expected_diff_contains and not diff:
                turn_passed = False
                issues.append("Expected diff elements but no diff was returned.")

            # 5. Check architecture preservation (ensuring parts of state or files are mentioned)
            if arch_preserved and response:
                for element in arch_preserved:
                    if element.lower() not in response.lower():
                        # Let's also check in diff or generated code
                        in_diff = diff and any(element.lower() in str(e).lower() for e in diff)
                        in_snapshot = snapshot and element.lower() in str(snapshot).lower()
                        if not (in_diff or in_snapshot):
                            issues.append(f"Warning: Preserved element '{element}' not found in response/diff/snapshot")

            if turn_passed:
                passed_turns += 1
                icon = "PASS"
            else:
                icon = "FAIL"
                scenario_passed = False

            print(f"    [{icon}] latency={latency:.2f}s | status={status} | turn={turn_num}")
            if issues:
                for issue in issues:
                    print(f"         ISSUE: {issue}")
            
            turns_results.append({
                "turn": turn_idx,
                "query": query,
                "status": status,
                "latency": latency,
                "passed": turn_passed,
                "issues": issues,
                "response_len": len(response)
            })

        print(f"Scenario {sid} Result: {'PASSED' if scenario_passed else 'FAILED'}\n")
        all_results.append({
            "id": sid,
            "description": desc,
            "passed": scenario_passed,
            "turns": turns_results
        })

    # Print summary report
    print_summary(all_results, total_turns, passed_turns)


def print_summary(all_results, total_turns, passed_turns):
    passed_scenarios = sum(1 for r in all_results if r["passed"])
    total_scenarios = len(all_results)
    
    lines = [
        "=" * 70,
        "  EMBEDDED COPILOT CONVERSATIONAL EVALUATION REPORT",
        f"  Time:   {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "=" * 70,
        f"  Total Scenarios  : {total_scenarios}",
        f"  Passed Scenarios : {passed_scenarios}  ({100*passed_scenarios//max(1,total_scenarios)}%)",
        f"  Total Turns      : {total_turns}",
        f"  Passed Turns     : {passed_turns}  ({100*passed_turns//max(1,total_turns)}%)",
        "=" * 70,
    ]

    lines.append("\n  Scenario Results:")
    lines.append(f"  {'Scenario ID':<15} {'Description':<35} {'Result':<8} {'Passed Turns'}")
    lines.append(f"  {'-'*70}")
    for r in all_results:
        res_str = "PASS" if r["passed"] else "FAIL"
        passed_t = sum(1 for t in r["turns"] if t["passed"])
        total_t = len(r["turns"])
        lines.append(f"  {r['id']:<15} {r['description'][:33]:<35} {res_str:<8} {passed_t}/{total_t}")

    # Log details of failures
    failures = [r for r in all_results if not r["passed"]]
    if failures:
        lines.append(f"\n  Failed Scenario Details:")
        for r in failures:
            lines.append(f"  [{r['id']}] {r['description']}")
            for t in r["turns"]:
                if not t["passed"]:
                    lines.append(f"    Turn {t['turn']} Query: \"{t['query']}\"")
                    for issue in t["issues"]:
                        lines.append(f"      -> {issue}")

    report_str = "\n".join(lines)
    print(report_str)

    # Save to a file
    report_file = r"c:\genai_project\backend\benchmarks\conversational_results.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_str)
    print(f"\nConversational evaluation summary saved to: {report_file}")


if __name__ == "__main__":
    run_conversational_tests()
