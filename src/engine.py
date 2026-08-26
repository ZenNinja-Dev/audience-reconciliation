"""
The deterministic reconciliation engine.

This module contains ZERO AI. Deciding what the Audience count *is* — which
Databricks rows belong to an account, whether they should be summed, whether the
data is fresh, whether a number is plausible — is a rules problem with real
money attached, so it is implemented as explicit, testable, auditable code.

The AI layer (src/explain.py) only turns these verdicts into human-readable
prose. It never changes a number or a status.

Pipeline per Salesforce account:
    1. Ambiguity guard   — is this customer_key shared by >1 SFDC account?
    2. Mapping           — resolve the SFDC key to a Databricks key (direct/alias/heuristic)
    3. Aggregation       — sum Databricks rows across business units
    4. Freshness         — is the newest source record recent enough to trust?
    5. Plausibility      — does the week-over-week trend look like real movement?
    6. Drift + verdict   — compare to the quoted number and assign a status
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from . import config
from .models import (
    Confidence,
    DbxCurrent,
    DbxHistory,
    ReconResult,
    SalesforceAccount,
    Status,
)


class ReconciliationEngine:
    def __init__(
        self,
        accounts: List[SalesforceAccount],
        dbx_current: List[DbxCurrent],
        dbx_history: List[DbxHistory],
        as_of=config.AS_OF,
    ):
        self.accounts = accounts
        self.as_of = as_of

        # Index Databricks current rows by customer_key.
        self.current_by_key: Dict[str, List[DbxCurrent]] = defaultdict(list)
        for rec in dbx_current:
            self.current_by_key[rec.customer_key].append(rec)

        # Index history rows by (customer_key, business_unit), sorted by date.
        self.history_by_key_bu: Dict[Tuple[str, str], List[DbxHistory]] = defaultdict(list)
        for rec in dbx_history:
            self.history_by_key_bu[(rec.customer_key, rec.business_unit)].append(rec)
        for rows in self.history_by_key_bu.values():
            rows.sort(key=lambda r: r.snapshot_date)

        # How many Salesforce accounts share each customer_key?
        self.key_usage: Dict[str, int] = defaultdict(int)
        for acc in accounts:
            self.key_usage[acc.customer_key] += 1

    # ------------------------------------------------------------------ #
    # Step 2 — mapping resolution
    # ------------------------------------------------------------------ #
    def _resolve_dbx_key(self, sfdc_key: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Return (databricks_key, resolution_note).
        resolution_note is None for a direct hit, otherwise a human-readable note.
        """
        if sfdc_key in self.current_by_key:
            return sfdc_key, None

        # 1. Explicit, maintained alias table (HIGH-confidence mapping).
        alias = config.ALIAS_MAP.get(sfdc_key)
        if alias and alias in self.current_by_key:
            return alias, f"alias table: {sfdc_key} -> {alias}"

        # 2. Conservative suffix heuristic for known key-drift patterns.
        for suffix in config.ALIAS_SUFFIX_CANDIDATES:
            candidate = f"{sfdc_key}{suffix}"
            if candidate in self.current_by_key:
                return candidate, f"suffix heuristic: {sfdc_key} -> {candidate}"

        return None, None

    # ------------------------------------------------------------------ #
    # Step 5 — plausibility (trend anomaly detection)
    # ------------------------------------------------------------------ #
    def _plausibility(self, dbx_key: str, business_units: List[str]):
        """
        Inspect week-over-week movement for each business unit's history.
        Returns (is_implausible, detail_or_None).
        """
        worst = None  # (abs_pct, bu, prev, latest, pct)
        for bu in business_units:
            rows = self.history_by_key_bu.get((dbx_key, bu), [])
            if len(rows) < 2:
                continue
            prev, latest = rows[-2].audience_count, rows[-1].audience_count
            if prev <= 0:
                continue
            pct = (latest - prev) / prev
            if worst is None or abs(pct) > abs(worst[4]):
                worst = (abs(pct), bu, prev, latest, pct)

        if worst and worst[0] > config.IMPLAUSIBLE_WOW_PCT:
            _, bu, prev, latest, pct = worst
            return True, {
                "business_unit": bu,
                "previous": prev,
                "latest": latest,
                "wow_pct": pct,
            }
        return False, None

    # ------------------------------------------------------------------ #
    # Main — reconcile one account
    # ------------------------------------------------------------------ #
    def reconcile_account(self, acc: SalesforceAccount) -> ReconResult:
        res = ReconResult(
            sfdc_account_id=acc.sfdc_account_id,
            account_name=acc.account_name,
            customer_key=acc.customer_key,
            status=Status.HOLD_NO_MATCH,
            confidence=Confidence.NONE,
            quoted_count=acc.last_quoted_audience_count,
        )

        # --- Step 1: ambiguity guard ------------------------------------
        if self.key_usage[acc.customer_key] > 1:
            res.status = Status.ESCALATE_AMBIGUOUS
            res.confidence = Confidence.NONE
            res.reasons.append(f"shared_customer_key:{self.key_usage[acc.customer_key]}")
            res.action_required = (
                "Do not auto-fill. Multiple Salesforce accounts share this "
                "Databricks key; the data team must split the key before a per-"
                "account Audience count can be trusted."
            )
            return res

        # --- Step 2: mapping --------------------------------------------
        dbx_key, note = self._resolve_dbx_key(acc.customer_key)
        if dbx_key is None:
            res.status = Status.HOLD_NO_MATCH
            res.confidence = Confidence.NONE
            res.reasons.append("no_dbx_match")
            res.action_required = (
                "Do not auto-fill. No Databricks Audience record maps to this "
                "account. Confirm the Databricks sync completed / the mapping "
                "exists, then re-run."
            )
            return res

        res.matched_dbx_key = dbx_key
        alias_used = note is not None
        if alias_used:
            res.reasons.append(f"alias_resolved:{dbx_key}")

        # --- Step 3: aggregation ----------------------------------------
        rows = self.current_by_key[dbx_key]
        breakdown = {r.business_unit: r.audience_count for r in rows}
        reconciled = sum(r.audience_count for r in rows)
        res.business_unit_breakdown = breakdown
        if len(rows) > 1:
            res.reasons.append(f"multi_bu_aggregation:{len(rows)}")

        # Age of the OLDEST contributing record (conservative).
        oldest_refresh = min(r.last_refreshed_at for r in rows)
        res.data_age_days = (self.as_of - oldest_refresh).days

        # --- Step 5: plausibility ---------------------------------------
        implausible, detail = self._plausibility(dbx_key, list(breakdown.keys()))

        # --- Step 4/6: freshness, drift, verdict ------------------------
        # Precedence: implausible > stale > drift comparison. An untrustworthy
        # number is never handed back as a count to quote against.
        if implausible:
            res.status = Status.REVIEW_IMPLAUSIBLE
            res.confidence = Confidence.LOW
            res.reconciled_count = None  # refuse to trust the current value
            res.reasons.append(f"implausible_wow:{detail['wow_pct']:.2f}")
            last_trusted = detail["previous"]
            res.action_required = (
                f"Do not trust the current value ({detail['latest']:,}). It jumped "
                f"{detail['wow_pct'] * 100:.0f}% week-over-week in '{detail['business_unit']}', "
                f"which looks like a data issue. Last trusted value was "
                f"{last_trusted:,}. Route to the data team before quoting."
            )
            return res

        if res.data_age_days is not None and res.data_age_days > config.STALE_AFTER_DAYS:
            res.status = Status.REVIEW_STALE
            res.confidence = Confidence.LOW
            res.reconciled_count = reconciled  # best available, clearly caveated
            res.reasons.append(f"stale_data:{res.data_age_days}d")
            res.action_required = (
                f"Databricks data is {res.data_age_days} days old (threshold "
                f"{config.STALE_AFTER_DAYS}). Treat {reconciled:,} as unconfirmed; "
                f"trigger a refresh or verify before sending the quote."
            )
            return res

        # Clean, fresh, plausible -> we have a trustworthy number.
        res.reconciled_count = reconciled
        base_conf = Confidence.MEDIUM if alias_used else Confidence.HIGH

        quoted = acc.last_quoted_audience_count
        if quoted:
            res.drift_pct = (reconciled - quoted) / quoted

        if quoted and abs(res.drift_pct) <= config.QUOTE_DRIFT_TOLERANCE:
            res.status = Status.MATCH
            res.confidence = base_conf
            res.reasons.append("clean_match")
            res.action_required = (
                "Quote count matches the current Databricks number. Safe to send."
                if not alias_used
                else "Counts match, but the account mapping was inferred — confirm "
                "the Databricks key mapping, then safe to send."
            )
        else:
            res.status = Status.REFRESH
            res.confidence = base_conf
            res.reasons.append("quote_out_of_date")
            drift_txt = (
                f"{res.drift_pct * 100:+.1f}% vs the quoted {quoted:,}"
                if quoted
                else "no count on the current quote"
            )
            res.action_required = (
                f"Update the quote to {reconciled:,} ({drift_txt})."
                + (" Confirm the inferred account mapping first." if alias_used else "")
            )

        return res

    def run(self) -> List[ReconResult]:
        return [self.reconcile_account(acc) for acc in self.accounts]
