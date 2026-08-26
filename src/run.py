"""
CLI entrypoint — the on-demand pre-quote validation slice.

Usage (from the repo root):
    python -m src.run                      # validate every account, print a report
    python -m src.run --account ACC-2007    # validate one account (the rep flow)
    python -m src.run --account "Solaris"  # match by name substring too
    python -m src.run --json               # emit machine-readable JSON

The single-account mode is the actual product surface: a rep about to send a
quote runs one check and gets back a number, a confidence, and a clear next
action — before the wrong number reaches a contract.
"""

import argparse
import json
import sys

from .data import load_dbx_current, load_dbx_history, load_salesforce_accounts
from .engine import ReconciliationEngine
from .explain import explain
from .models import ACTIONABLE, Confidence, Status

# Status -> a short tag for the plain-text report.
STATUS_TAG = {
    Status.MATCH: "OK",
    Status.REFRESH: "REFRESH",
    Status.REVIEW_STALE: "REVIEW",
    Status.REVIEW_IMPLAUSIBLE: "REVIEW",
    Status.HOLD_NO_MATCH: "HOLD",
    Status.ESCALATE_AMBIGUOUS: "ESCALATE",
}


def _fmt(n):
    return f"{n:,}" if isinstance(n, int) else "—"


def print_one(res, verbose=True):
    safe = "yes" if res.status in ACTIONABLE and res.confidence == Confidence.HIGH else "NO"
    print(f"  Account        : {res.account_name}  ({res.sfdc_account_id})")
    print(f"  Customer key   : {res.customer_key}"
          + (f"  ->  Databricks {res.matched_dbx_key}"
             if res.matched_dbx_key and res.matched_dbx_key != res.customer_key else ""))
    print(f"  Status         : {res.status.value}   (confidence: {res.confidence.value})")
    print(f"  Quoted count   : {_fmt(res.quoted_count)}")
    print(f"  Reconciled     : {_fmt(res.reconciled_count)}"
          + (f"   (drift {res.drift_pct * 100:+.1f}%)" if res.drift_pct is not None else ""))
    if len(res.business_unit_breakdown) > 1:
        parts = ", ".join(f"{k}={v:,}" for k, v in res.business_unit_breakdown.items())
        print(f"  BU breakdown   : {parts}")
    if res.data_age_days is not None:
        print(f"  Data age       : {res.data_age_days} days")
    print(f"  Safe to quote? : {safe}")
    print(f"  Action         : {res.action_required}")
    if verbose:
        print(f"  Explanation    : {explain(res)}")
    print(f"  Reason codes   : {', '.join(res.reasons) or '—'}")


def build_engine():
    accounts = load_salesforce_accounts()
    engine = ReconciliationEngine(
        accounts, load_dbx_current(), load_dbx_history()
    )
    return accounts, engine


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audience pre-quote validation.")
    parser.add_argument("--account", help="Filter by customer_key, SFDC id, or name substring.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a report.")
    args = parser.parse_args(argv)

    accounts, engine = build_engine()
    results = engine.run()

    if args.account:
        needle = args.account.lower()
        results = [
            r for r in results
            if needle in r.customer_key.lower()
            or needle in r.sfdc_account_id.lower()
            or needle in r.account_name.lower()
        ]
        if not results:
            print(f"No account matches {args.account!r}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return 0

    # ---- human-readable report ----
    print("=" * 78)
    print("AUDIENCE PRE-QUOTE VALIDATION  —  reconciliation report")
    print("=" * 78)

    # One-line-per-account summary table first.
    print(f"\n{'STATUS':<9} {'SAFE':<5} {'ACCOUNT':<26} {'QUOTED':>10} {'RECONCILED':>12}")
    print("-" * 78)
    for r in results:
        safe = "yes" if r.status in ACTIONABLE and r.confidence == Confidence.HIGH else "no"
        print(f"{STATUS_TAG[r.status]:<9} {safe:<5} {r.account_name[:26]:<26} "
              f"{_fmt(r.quoted_count):>10} {_fmt(r.reconciled_count):>12}")

    # Then the detail for each.
    for r in results:
        print("\n" + "-" * 78)
        print_one(r)

    # Summary counters.
    print("\n" + "=" * 78)
    from collections import Counter
    counts = Counter(r.status.value for r in results)
    safe_n = sum(1 for r in results
                 if r.status in ACTIONABLE and r.confidence == Confidence.HIGH)
    print(f"Accounts checked: {len(results)}   |   Safe to auto-use: {safe_n}   |   "
          f"Needs a human: {len(results) - safe_n}")
    print("Breakdown: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
