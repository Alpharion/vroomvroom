"""Phase 6: Consistency and fairness tests.

Runs TC-05 five times to measure outcome consistency, then runs
TC-05 with --driver-first to test that brief ordering does not
affect the outcome (E-1.2 fairness check).

Usage (from backend/):
    USE_MOCK_LLM=false python scripts/run_phase6_metrics.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from agents.pipeline import resolve_case
from app.main import _CASE_INDEX
import os

# Suppress the DISP-003 warning by setting logging level
import logging
logging.getLogger("app.main").setLevel(logging.ERROR)


async def run_case(case_id: str, driver_first: bool = False) -> dict:
    case = _CASE_INDEX[case_id]
    start = time.monotonic()
    result = await resolve_case(case, driver_first=driver_first)
    elapsed = time.monotonic() - start
    ruling = result["ruling"]
    return {
        "case_id": case_id,
        "outcome": ruling.outcome,
        "amount_sgd": ruling.amount_sgd,
        "confidence": ruling.confidence,
        "clauses_cited": ruling.clauses_cited,
        "driver_first": driver_first,
        "duration_s": round(elapsed, 1),
    }


async def main():
    print("=" * 70)
    print("  Phase 6: Consistency & Fairness Tests")
    print("=" * 70)
    print(f"  USE_MOCK_LLM={os.environ.get('USE_MOCK_LLM', 'not set')}")
    print(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()

    # --- Consistency: TC-05 five times ---
    print("  [1] Consistency: Running TC-05 five times (rider-first)...")
    consistency_results = []
    for i in range(5):
        r = await run_case("TC-05", driver_first=False)
        consistency_results.append(r)
        print(f"    Run {i+1}: {r['outcome']} ${r['amount_sgd']:.2f} "
              f"conf={r['confidence']:.2f} ({r['duration_s']}s)")

    outcomes = [r["outcome"] for r in consistency_results]
    amounts = [r["amount_sgd"] for r in consistency_results]
    confidences = [r["confidence"] for r in consistency_results]
    durations = [r["duration_s"] for r in consistency_results]

    unique_outcomes = set(outcomes)
    unique_amounts = set(round(a, 2) for a in amounts)

    print(f"\n  Consistency summary:")
    print(f"    Outcomes: {outcomes} -> {'CONSISTENT' if len(unique_outcomes)==1 else 'INCONSISTENT'}")
    print(f"    Amounts:  {[f'${a:.2f}' for a in amounts]} -> {'CONSISTENT' if len(unique_amounts)==1 else 'INCONSISTENT'}")
    print(f"    Conf range: {min(confidences):.2f} - {max(confidences):.2f}")
    print(f"    Duration mean: {sum(durations)/len(durations):.1f}s, "
          f"min: {min(durations):.1f}s, max: {max(durations):.1f}s")

    # --- Fairness: --driver-first ---
    print(f"\n  [2] Fairness: Running TC-05 with --driver-first...")
    df_result = await run_case("TC-05", driver_first=True)
    print(f"    driver_first: {df_result['outcome']} ${df_result['amount_sgd']:.2f} "
          f"conf={df_result['confidence']:.2f} ({df_result['duration_s']}s)")
    print(f"    rider_first:  {consistency_results[0]['outcome']} ${consistency_results[0]['amount_sgd']:.2f} "
          f"conf={consistency_results[0]['confidence']:.2f} ({consistency_results[0]['duration_s']}s)")

    if df_result["outcome"] == consistency_results[0]["outcome"] and \
       abs(df_result["amount_sgd"] - consistency_results[0]["amount_sgd"]) < 0.01:
        print("    -> PASS: Outcome and amount unchanged regardless of brief order (E-1.2)")
    else:
        print("    -> FAIL: Outcome or amount changed with brief order!")

    # --- Fairness: TC-01 vs TC-10 (profile swap) ---
    print(f"\n  [3] Fairness: TC-01 vs TC-10 (profile swap)...")
    # These were already run in the live suite; we have them in .live_results.json
    live_path = _BACKEND_DIR / ".live_results.json"
    live = json.loads(live_path.read_text(encoding="utf-8"))
    tc01 = next(r for r in live if r["case_id"] == "TC-01")
    tc10 = next(r for r in live if r["case_id"] == "TC-10")
    print(f"    TC-01: {tc01['outcome']} ${tc01['amount_sgd']:.2f} conf={tc01['confidence']:.2f}")
    print(f"    TC-10: {tc10['outcome']} ${tc10['amount_sgd']:.2f} conf={tc10['confidence']:.2f}")
    if tc01["outcome"] == tc10["outcome"] and tc01["amount_sgd"] == tc10["amount_sgd"]:
        print("    -> PASS: Same outcome despite swapped rider/driver profiles (E-1.5)")
    else:
        print("    -> FAIL: Outcome differs with swapped profiles!")

    # --- Full suite duration stats ---
    print(f"\n  [4] Full suite duration statistics (from .live_results.json)...")
    durations_all = [r["duration_s"] for r in live]
    d_sorted = sorted(durations_all)
    n = len(d_sorted)
    mean = sum(d_sorted) / n
    median = d_sorted[n // 2]
    p95_idx = int(0.95 * (n - 1))
    p95 = d_sorted[p95_idx]
    print(f"    n={n}, mean={mean:.1f}s, median={median:.1f}s, p95={p95:.1f}s")
    print(f"    min={min(d_sorted):.1f}s, max={max(d_sorted):.1f}s")
    print(f"    total={sum(d_sorted):.1f}s")

    # Save Phase 6 results
    phase6 = {
        "consistency_tc05": consistency_results,
        "fairness_driver_first": df_result,
        "fairness_tc01_vs_tc10": {
            "tc01": {"outcome": tc01["outcome"], "amount_sgd": tc01["amount_sgd"],
                      "confidence": tc01["confidence"]},
            "tc10": {"outcome": tc10["outcome"], "amount_sgd": tc10["amount_sgd"],
                      "confidence": tc10["confidence"]},
            "outcome_match": tc01["outcome"] == tc10["outcome"],
            "amount_match": tc01["amount_sgd"] == tc10["amount_sgd"],
        },
        "duration_stats": {
            "n": n, "mean": round(mean, 1), "median": median,
            "p95": p95, "min": min(d_sorted), "max": max(d_sorted),
            "total": round(sum(d_sorted), 1),
        },
    }
    out_path = _BACKEND_DIR / ".phase6_results.json"
    out_path.write_text(json.dumps(phase6, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Results saved to {out_path}")
    print(f"  Finished: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")


if __name__ == "__main__":
    asyncio.run(main())
