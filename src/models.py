"""Typed data structures shared across the engine. Pure stdlib (dataclasses)."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Status(str, Enum):
    """
    The verdict the engine returns for one Salesforce account.

    Only MATCH and REFRESH are ever safe for a rep to act on without a human
    check. Everything else routes to review or escalation — a wrong count feeds
    a wrong price.
    """

    MATCH = "MATCH"                          # quote count == reconciled count (within tolerance)
    REFRESH = "REFRESH"                      # trustworthy count, but quote is out of date -> update it
    REVIEW_STALE = "REVIEW_STALE"            # Databricks data too old to trust as "current"
    REVIEW_IMPLAUSIBLE = "REVIEW_IMPLAUSIBLE"  # trend anomaly -> current value not trustworthy
    HOLD_NO_MATCH = "HOLD_NO_MATCH"          # no Databricks record -> cannot validate
    ESCALATE_AMBIGUOUS = "ESCALATE_AMBIGUOUS"  # shared key / cannot attribute -> human must resolve


class Confidence(str, Enum):
    HIGH = "HIGH"      # clean, fresh, plausible, unambiguous
    MEDIUM = "MEDIUM"  # resolved via a heuristic (e.g. alias) — confirm before trusting
    LOW = "LOW"        # stale or implausible — do not trust as-is
    NONE = "NONE"      # no defensible number could be produced


# Statuses a rep may act on directly (auto-suggest the number in the quote).
ACTIONABLE = {Status.MATCH, Status.REFRESH}


@dataclass
class SalesforceAccount:
    sfdc_account_id: str
    account_name: str
    customer_key: str
    region: str
    pricing_tier: str
    last_quoted_audience_count: Optional[int]
    last_quote_date: Optional[date]
    renewal_date: Optional[date]
    account_notes: str


@dataclass
class DbxCurrent:
    databricks_record_id: str
    customer_key: str
    business_unit: str
    audience_count: int
    last_refreshed_at: date


@dataclass
class DbxHistory:
    customer_key: str
    business_unit: str
    snapshot_date: date
    audience_count: int


@dataclass
class ReconResult:
    """One reconciliation verdict for one Salesforce account."""

    sfdc_account_id: str
    account_name: str
    customer_key: str
    status: Status
    confidence: Confidence

    quoted_count: Optional[int] = None
    reconciled_count: Optional[int] = None   # the number we'd put in the quote, if any
    drift_pct: Optional[float] = None        # (reconciled - quoted) / quoted

    matched_dbx_key: Optional[str] = None    # key actually used to join (may differ from SFDC key)
    business_unit_breakdown: dict = field(default_factory=dict)  # BU -> count (for aggregation)
    data_age_days: Optional[int] = None      # age of the freshest DBX record used

    reasons: list = field(default_factory=list)   # machine-readable reason codes
    action_required: str = ""                     # what a human/rep should do next
    explanation: str = ""                         # human-readable narrative (AI or template)

    def to_dict(self) -> dict:
        return {
            "sfdc_account_id": self.sfdc_account_id,
            "account_name": self.account_name,
            "customer_key": self.customer_key,
            "status": self.status.value,
            "confidence": self.confidence.value,
            "quoted_count": self.quoted_count,
            "reconciled_count": self.reconciled_count,
            "drift_pct": round(self.drift_pct, 4) if self.drift_pct is not None else None,
            "matched_dbx_key": self.matched_dbx_key,
            "business_unit_breakdown": self.business_unit_breakdown,
            "data_age_days": self.data_age_days,
            "reasons": self.reasons,
            "action_required": self.action_required,
            "explanation": self.explanation,
        }
