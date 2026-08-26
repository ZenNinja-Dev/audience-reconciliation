"""
Focused unit tests for the deterministic pieces of the engine.

Stdlib unittest only — no pytest, no install. Run from the repo root:
    python -m unittest discover -s tests -v

The end-to-end behaviour is covered by `python -m eval.run_eval`; these tests
pin the small building blocks so a regression points at the exact rule.
"""

import unittest
from datetime import date

from src.data import _to_date, _to_int
from src.engine import ReconciliationEngine
from src.models import Confidence, DbxCurrent, DbxHistory, SalesforceAccount, Status


def _acc(key, quoted, name="Test", sid=None):
    return SalesforceAccount(
        sfdc_account_id=sid or f"SID-{key}",
        account_name=name,
        customer_key=key,
        region="NA",
        pricing_tier="Tier 2",
        last_quoted_audience_count=quoted,
        last_quote_date=date(2026, 4, 1),
        renewal_date=date(2026, 9, 1),
        account_notes="",
    )


def _cur(key, bu, count, refreshed=date(2026, 7, 1)):
    return DbxCurrent(f"DBX-{key}-{bu}", key, bu, count, refreshed)


def _hist(key, bu, *pairs):
    return [DbxHistory(key, bu, d, c) for d, c in pairs]


class ParsingTests(unittest.TestCase):
    def test_int_handles_blank_and_float(self):
        self.assertIsNone(_to_int(""))
        self.assertEqual(_to_int("149800"), 149800)
        self.assertEqual(_to_int("149800.0"), 149800)

    def test_date_handles_both_formats(self):
        self.assertEqual(_to_date("2026-07-01"), date(2026, 7, 1))
        self.assertEqual(_to_date("2026-07-01 06:12:00"), date(2026, 7, 1))
        self.assertIsNone(_to_date(""))


class EngineRuleTests(unittest.TestCase):
    def test_clean_match_within_tolerance(self):
        eng = ReconciliationEngine([_acc("CK-A", 1000)], [_cur("CK-A", "Retail", 1000)], [])
        r = eng.run()[0]
        self.assertEqual(r.status, Status.MATCH)
        self.assertEqual(r.confidence, Confidence.HIGH)

    def test_multi_bu_is_summed_not_averaged(self):
        eng = ReconciliationEngine(
            [_acc("CK-B", 480000)],
            [_cur("CK-B", "NA", 312400), _cur("CK-B", "EMEA", 141900), _cur("CK-B", "APAC", 88300)],
            [],
        )
        r = eng.run()[0]
        self.assertEqual(r.reconciled_count, 542600)
        self.assertEqual(r.status, Status.REFRESH)

    def test_missing_match_never_invents_a_number(self):
        eng = ReconciliationEngine([_acc("CK-GONE", 72000)], [], [])
        r = eng.run()[0]
        self.assertEqual(r.status, Status.HOLD_NO_MATCH)
        self.assertIsNone(r.reconciled_count)

    def test_stale_data_is_flagged_low_confidence(self):
        eng = ReconciliationEngine(
            [_acc("CK-S", 59500)],
            [_cur("CK-S", "Media", 61900, refreshed=date(2026, 5, 10))],
            [],
        )
        r = eng.run()[0]
        self.assertEqual(r.status, Status.REVIEW_STALE)
        self.assertEqual(r.confidence, Confidence.LOW)

    def test_implausible_spike_is_not_trusted(self):
        eng = ReconciliationEngine(
            [_acc("CK-I", 8100)],
            [_cur("CK-I", "Digital", 486200)],
            _hist("CK-I", "Digital",
                  (date(2026, 6, 17), 9100), (date(2026, 6, 24), 9600), (date(2026, 7, 1), 486200)),
        )
        r = eng.run()[0]
        self.assertEqual(r.status, Status.REVIEW_IMPLAUSIBLE)
        self.assertIsNone(r.reconciled_count)

    def test_shared_key_is_ambiguous_for_both(self):
        eng = ReconciliationEngine(
            [_acc("CK-D", 80000, "Sable Industries", "SID-1"),
             _acc("CK-D", 75000, "Sable Analytics", "SID-2")],
            [_cur("CK-D", "Combined Legacy", 155000)],
            [],
        )
        for r in eng.run():
            self.assertEqual(r.status, Status.ESCALATE_AMBIGUOUS)

    def test_alias_suffix_resolves_but_stays_medium_confidence(self):
        eng = ReconciliationEngine(
            [_acc("CK-8", 95000)],
            [_cur("CK-8-OLD", "CPG", 97300)],
            [],
        )
        r = eng.run()[0]
        self.assertEqual(r.matched_dbx_key, "CK-8-OLD")
        self.assertEqual(r.confidence, Confidence.MEDIUM)  # inferred mapping -> not auto-safe


if __name__ == "__main__":
    unittest.main()
