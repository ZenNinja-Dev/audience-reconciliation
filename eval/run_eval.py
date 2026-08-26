"""
Eval runner.

Loads the expectations in eval_cases.json, runs the engine over the mock
dataset, and asserts the verdict for every account: status, confidence, and
whether it is safe to auto-use. Exits non-zero if anything regresses, so this
doubles as a CI gate.

Run from the repo root:
    python -m eval.run_eval
"""

import json
import sys
from pathlib import Path

from src.data import load_dbx_current, load_dbx_history, load_salesforce_accounts
from src.engine import ReconciliationEngine
from src.models import ACTIONABLE, Confidence

CASES_PATH = Path(__file__).resolve().parent / "eval_cases.json"


def is_safe(res) -> bool:
    return res.status in ACTIONABLE and res.confidence == Confidence.HIGH


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    engine = ReconciliationEngine(
        load_salesforce_accounts(), load_dbx_current(), load_dbx_history()
    )
    by_id = {r.sfdc_account_id: r for r in engine.run()}

    print("=" * 92)
    print("EVAL — expected vs actual reconciliation verdicts")
    print("=" * 92)
    print(f"{'RESULT':<7} {'ACCOUNT':<26} {'CATEGORY':<22} {'EXPECTED':<20} {'ACTUAL':<20}")
    print("-" * 92)

    passed = failed = 0
    failures = []

    for case in cases:
        res = by_id.get(case["sfdc_account_id"])
        checks = []

        if res is None:
            checks.append(("engine returned no result", False))
        else:
            checks.append((
                f"status {res.status.value}",
                res.status.value == case["expected_status"],
            ))
            if "expected_confidence" in case:
                checks.append((
                    f"confidence {res.confidence.value}",
                    res.confidence.value == case["expected_confidence"],
                ))
            checks.append((
                f"safe={is_safe(res)}",
                is_safe(res) == case["expected_safe"],
            ))

        ok = all(c[1] for c in checks)
        passed += ok
        failed += (not ok)

        actual = res.status.value if res else "—"
        actual += f"/{res.confidence.value}" if res else ""
        expected = case["expected_status"]
        expected += f"/{case.get('expected_confidence', '?')}"

        print(f"{'PASS' if ok else 'FAIL':<7} {case['account_name'][:26]:<26} "
              f"{case['category']:<22} {expected:<20} {actual:<20}")
        if not ok:
            failures.append((case, [c for c in checks if not c[1]]))

    print("-" * 92)
    print(f"TOTAL: {passed} passed, {failed} failed, {len(cases)} cases")
    print("=" * 92)

    if failures:
        print("\nFAILURE DETAIL")
        for case, bad in failures:
            print(f"  {case['account_name']} ({case['sfdc_account_id']}):")
            for label, _ in bad:
                print(f"    - mismatch: {label}")
        return 1

    print("\nAll expectations met. See eval_cases.md for the reasoning behind each case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
