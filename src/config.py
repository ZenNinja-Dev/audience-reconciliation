"""
Configuration and business rules for the reconciliation engine.

Everything that a business stakeholder might argue about lives here, on purpose.
Counting Audience is a *rules* problem before it is ever an AI problem, so the
rules are explicit, versioned config — not buried in code and not delegated to a
model. Changing a threshold is a config change with a clear blast radius, not a
prompt tweak with unpredictable behaviour.
"""

from datetime import date

# ---------------------------------------------------------------------------
# "Now" for the exercise.
# The mock Databricks snapshot is taken as-of 2026-07-01 (see synthetic_data/
# README.md). We freeze the engine's notion of "today" to that date so runs are
# deterministic and reviewers get identical output. In production this would be
# date.today() (or the pipeline run timestamp).
# ---------------------------------------------------------------------------
AS_OF = date(2026, 7, 1)

# ---------------------------------------------------------------------------
# Freshness: how old a Databricks record may be before we stop trusting it as
# "current". Contract pricing is tied to a live number, so a 7-week-old snapshot is
# not something a rep should quote against blindly.
# ---------------------------------------------------------------------------
STALE_AFTER_DAYS = 14

# ---------------------------------------------------------------------------
# Plausibility: a week-over-week relative change above this magnitude is treated
# as "implausible / likely a data issue" rather than real audience movement, and
# the current value is flagged instead of trusted. 3.0 == 300%.
# Tuned to pass normal single-digit-percent weekly growth and catch a 49x jump.
# ---------------------------------------------------------------------------
IMPLAUSIBLE_WOW_PCT = 3.0

# ---------------------------------------------------------------------------
# Quote drift tolerance: how far the count on the last quote may sit from the
# reconciled current count before we recommend refreshing the quote. 0.02 == 2%.
# Below this we call it a MATCH (quote still safe to send).
# ---------------------------------------------------------------------------
QUOTE_DRIFT_TOLERANCE = 0.02

# ---------------------------------------------------------------------------
# Account-mapping alias rules.
#
# Salesforce customer_key does not always equal the Databricks customer_key.
# Two deterministic resolution strategies, in order:
#   1. Explicit alias map (a maintained mapping table — the right long-term fix).
#   2. A conservative suffix heuristic for known drift patterns (e.g. a key that
#      was frozen as "<key>-OLD" after a rebrand). Heuristic matches are marked
#      MEDIUM confidence and always tell the human what was assumed.
#
# We deliberately do NOT fuzzy-match on account name here: a wrong join feeds a
# wrong price. Unknown mappings are escalated, not guessed.
# ---------------------------------------------------------------------------
ALIAS_MAP = {
    # sfdc_customer_key: databricks_customer_key
    # (empty by default — ACC-2008 is resolved by the suffix heuristic below so
    #  the heuristic path is exercised; add confirmed mappings here to promote
    #  them to HIGH confidence.)
}

# Suffix variants tried when a Salesforce key has no direct Databricks match.
ALIAS_SUFFIX_CANDIDATES = ["-OLD", "-LEGACY", "-NEW"]
