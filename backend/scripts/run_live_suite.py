"""Run TC-01 through TC-15 against live ADP and collect results.

Usage (from backend/):
    USE_MOCK_LLM=false python scripts/run_live_suite.py

Writes results to docs/live-integration-results.md
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

# Load expected results
_expected_path = _REPO_ROOT / "data" / "test_cases" / "expected_results.json"
_expected = json.loads(_expected_path.read_text(encoding="utf-8"))
_expected_map = {tc["case_id"]: tc for tc in _expected["test_cases"]}

# Also load DISP-001 expected
_disp001_expected = json.loads(
    (_REPO_ROOT / "data" / "DISP-001.expected.json").read_text(encoding="utf-8")
)


async def run_one(case_id: str) -> dict:
    """Run one case live and return a result dict."""
    case = _CASE_INDEX.get(case_id)
    if case is None:
        return {"case_id": case_id, "error": "Case not found in index"}

    dispute_id = case.dispute_ticket.dispute_id
    dispute_type = case.dispute_ticket.dispute_type

    start = time.monotonic()
    try:
        result = await resolve_case(case)
        elapsed = time.monotonic() - start
        ruling = result["ruling"]
        return {
            "case_id": case_id,
            "dispute_id": dispute_id,
            "dispute_type": dispute_type,
            "outcome": ruling.outcome,
            "amount_sgd": ruling.amount_sgd,
            "confidence": ruling.confidence,
            "escalated": ruling.escalated,
            "clauses_cited": ruling.clauses_cited,
            "escalation_reason": ruling.escalation_reason,
            "duration_s": round(elapsed, 1),
            "error": None,
        }
    except Exception as e:
        elapsed = time.monotonic() - start
        return {
            "case_id": case_id,
            "dispute_id": dispute_id,
            "dispute_type": dispute_type,
            "error": str(e),
            "duration_s": round(elapsed, 1),
        }


async def main():
    case_ids = [f"TC-{i:02d}" for i in range(1, 16)]

    print("=" * 70)
    print("  Live ADP Integration Test Suite — TC-01 through TC-15")
    print("=" * 70)
    print(f"  USE_MOCK_LLM={os.environ.get('USE_MOCK_LLM', 'not set')}")
    print(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()

    results = []
    for cid in case_ids:
        print(f"  Running {cid}...", flush=True, end=" ")
        r = await run_one(cid)
        results.append(r)
        if r.get("error"):
            print(f"ERROR: {r['error'][:80]} ({r['duration_s']}s)")
        else:
            exp = _expected_map.get(cid, {})
            exp_outcome = exp.get("expected_verdict", "?")
            exp_amount = exp.get("expected_amount_sgd")
            match = "PASS" if r["outcome"] == exp_outcome else "FAIL"
            amt_match = ""
            if exp_amount is not None and r.get("amount_sgd") is not None:
                amt_match = f" ${r['amount_sgd']:.2f} vs ${exp_amount:.2f}"
                if abs(r["amount_sgd"] - exp_amount) > 0.01:
                    match = "FAIL"
            print(f"{match} {r['outcome']} ${r.get('amount_sgd', 0):.2f} "
                  f"conf={r['confidence']:.2f} ({r['duration_s']}s)")

    # Write JSON results for the doc generator
    out_path = _BACKEND_DIR / ".live_results.json"
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  Results saved to {out_path}")
    print(f"  Finished: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")


if __name__ == "__main__":
    asyncio.run(main())
