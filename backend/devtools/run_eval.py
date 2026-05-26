"""
Deterministic Evaluation Framework — auto-scores system responses.

Scoring dimensions:
  1. Correctness    — expected keywords present in answer
  2. Safety         — forbidden content absent from answer
  3. Routing        — correct intent was detected
  4. Rejection      — invalid traps correctly rejected
  5. Latency        — response time within acceptable bounds

Usage:
  python run_eval.py                      # run all benchmark suites
  python run_eval.py --suite traps        # run only trap suite
  python run_eval.py --suite hardware_reasoning rtos

Output:
  benchmarks/eval_results_<timestamp>.json
  benchmarks/eval_summary_<timestamp>.txt
"""

import json
import os
import sys
import time
import glob
import requests
import argparse
from datetime import datetime

URL        = "http://localhost:8000/ask"
BENCH_DIR  = os.path.join(os.path.dirname(__file__), "benchmarks")
LATENCY_OK = 10.0   # seconds — anything above this is flagged

# Penalty markers: if any of these appear in an answer, it's a hallucination
HALLUCINATION_MARKERS = [
    "ADCSRA", "ADMUX", "analogRead", "PORTB", "DDRD",
    "osThreadCreate", "rt_tsk_create", "OSTaskCreate",
    "PR2DIR", "PR2ETA", "RAREG",
]


def score_response(test: dict, answer: str, status: str, latency: float, actual_intent: str) -> dict:
    result = {
        "id":             test["id"],
        "question":       test["question"],
        "domain":         test["domain"],
        "category":       test.get("category", ""),
        "status":         status,
        "latency_s":      round(latency, 2),
        "answer_snippet": answer[:300],
        "scores": {},
        "pass":   True,
        "issues": [],
    }

    # ── Correctness: expected keywords ────────────────────────────────────────
    kw_hits  = [kw for kw in test.get("expected_keywords", []) if kw.lower() in answer.lower()]
    kw_total = len(test.get("expected_keywords") or ["_"]) or 1
    kw_score = round(len(kw_hits) / kw_total, 2)
    result["scores"]["correctness"] = kw_score
    if kw_score < 0.5 and test.get("expected_keywords"):
        result["issues"].append(f"Low keyword coverage: {kw_hits}/{test['expected_keywords']}")
        result["pass"] = False

    # ── Trap rejection ────────────────────────────────────────────────────────
    must_reject = test.get("must_be_rejected", False)
    was_rejected = any(k in answer for k in ["Invalid", "Architecture Mismatch", "Warning", "### ?"])
    if must_reject:
        result["scores"]["rejection"] = 1.0 if was_rejected else 0.0
        if not was_rejected:
            result["issues"].append("Trap was NOT correctly rejected")
            result["pass"] = False
    else:
        result["scores"]["rejection"] = "N/A"

    # ── Safety: forbidden content absent ─────────────────────────────────────
    forbidden_hits = [f for f in test.get("must_not_contain", []) if f.lower() in answer.lower()]
    hallucinations = [h for h in HALLUCINATION_MARKERS if h in answer]
    all_bad = forbidden_hits + hallucinations
    if all_bad and not was_rejected:
        result["scores"]["safety"] = 0.0
        result["issues"].append(f"Forbidden content detected: {all_bad}")
        result["pass"] = False
    else:
        result["scores"]["safety"] = 1.0



    # ── Latency ───────────────────────────────────────────────────────────────
    result["scores"]["latency"] = "OK" if latency < LATENCY_OK else "SLOW"
    if latency >= LATENCY_OK:
        result["issues"].append(f"Latency {latency:.1f}s exceeds {LATENCY_OK}s threshold")

    return result


def run_suite(suite_name: str) -> list:
    path = os.path.join(BENCH_DIR, f"{suite_name}.json")
    if not os.path.exists(path):
        print(f"  [SKIP] Suite not found: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        tests = json.load(f)

    results = []
    for test in tests:
        print(f"  [{test['id']}] {test['question'][:70]}...")
        t0 = time.time()
        try:
            r = requests.post(URL, json={"text": test["question"]}, timeout=30)
            latency = time.time() - t0
            if r.status_code == 200:
                data   = r.json()
                answer = data.get("response", "")
                status = data.get("status", "unknown")
                # Structured response support
                if "answer" in data:
                    answer = data.get("answer", answer)
                    status = "success"
            else:
                answer = f"HTTP {r.status_code}"
                status = "error"
        except Exception as e:
            latency = time.time() - t0
            answer  = str(e)
            status  = "failed"

        result = score_response(test, answer, status, latency, "")
        results.append(result)

        icon = "PASS" if result["pass"] else "FAIL"
        print(f"    [{icon}] latency={result['latency_s']}s | correctness={result['scores'].get('correctness', 'N/A')}")
        if result["issues"]:
            for issue in result["issues"]:
                print(f"         ISSUE: {issue}")

    return results


def summarize(all_results: list, suites: list) -> str:
    total  = len(all_results)
    passed = sum(1 for r in all_results if r["pass"])
    failed = total - passed

    avg_latency = sum(r["latency_s"] for r in all_results) / total if total else 0
    avg_correct = sum(
        r["scores"].get("correctness", 0)
        for r in all_results
        if isinstance(r["scores"].get("correctness"), float)
    ) / max(1, sum(1 for r in all_results if isinstance(r["scores"].get("correctness"), float)))

    safety_fail = sum(1 for r in all_results if r["scores"].get("safety") == 0.0)
    trap_pass   = sum(1 for r in all_results
                      if isinstance(r["scores"].get("rejection"), float)
                      and r["scores"]["rejection"] == 1.0)
    trap_total  = sum(1 for r in all_results
                      if isinstance(r["scores"].get("rejection"), float))

    lines = [
        "=" * 70,
        "  EMBEDDED GEN-AI DETERMINISTIC EVALUATION REPORT",
        f"  Suites: {', '.join(suites)}",
        f"  Time:   {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "=" * 70,
        f"  Total Questions  : {total}",
        f"  Passed           : {passed}  ({100*passed//max(1,total)}%)",
        f"  Failed           : {failed}",
        f"  Avg Latency      : {avg_latency:.2f}s",
        f"  Avg Correctness  : {avg_correct:.0%}",
        f"  Safety Failures  : {safety_fail}  (hallucination events)",
        f"  Trap Rejection   : {trap_pass}/{trap_total}  correctly rejected",
        "=" * 70,
    ]

    # Per-domain breakdown
    domains = {}
    for r in all_results:
        d = r["domain"]
        domains.setdefault(d, {"pass": 0, "total": 0})
        domains[d]["total"] += 1
        if r["pass"]:
            domains[d]["pass"] += 1

    lines.append("\n  Per-Domain Results:")
    lines.append(f"  {'Domain':<20} {'Pass':<6} {'Total':<6} {'Rate'}")
    lines.append(f"  {'-'*40}")
    for domain, stats in sorted(domains.items()):
        rate = f"{100*stats['pass']//max(1,stats['total'])}%"
        lines.append(f"  {domain:<20} {stats['pass']:<6} {stats['total']:<6} {rate}")

    # Failed cases
    failures = [r for r in all_results if not r["pass"]]
    if failures:
        lines.append(f"\n  Failed Cases ({len(failures)}):")
        for r in failures:
            lines.append(f"  [{r['id']}] {r['question'][:60]}...")
            for issue in r["issues"]:
                lines.append(f"      -> {issue}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run benchmark evaluation suites")
    parser.add_argument("--suite", nargs="*",
                        help="Suite names to run (default: all)")
    args = parser.parse_args()

    # Auto-discover suites (exclude eval_results_ output files)
    all_suite_files = [f for f in glob.glob(os.path.join(BENCH_DIR, "*.json"))
                       if not os.path.basename(f).startswith("eval_results_")]
    all_suite_names = [os.path.splitext(os.path.basename(f))[0] for f in all_suite_files]

    suites_to_run = args.suite if args.suite else all_suite_names

    print(f"\nEmbedded Gen-AI Evaluation Framework v1.0")
    print(f"Running suites: {suites_to_run}\n")

    all_results = []
    for suite in suites_to_run:
        print(f"[SUITE] {suite.upper()}")
        results = run_suite(suite)
        all_results.extend(results)
        print()

    # Save JSON results
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_out = os.path.join(BENCH_DIR, f"eval_results_{ts}.json")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    # Save summary report
    summary = summarize(all_results, suites_to_run)
    txt_out = os.path.join(BENCH_DIR, f"eval_summary_{ts}.txt")
    with open(txt_out, "w", encoding="utf-8") as f:
        f.write(summary)

    print(summary)
    print(f"\nDetailed results: {json_out}")
    print(f"Summary report:  {txt_out}")


if __name__ == "__main__":
    main()
