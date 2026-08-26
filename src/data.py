"""
Data loading layer.

The prototype reads the mock CSVs directly. In production these three readers
are the *only* things that change: `load_salesforce_accounts` becomes a
Salesforce report/API pull and the two Databricks readers become a Genie /
SQL warehouse query. The engine downstream does not care where the rows came
from, which keeps the integration surface small and testable.
"""

import csv
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from .models import DbxCurrent, DbxHistory, SalesforceAccount

DATA_DIR = Path(__file__).resolve().parent.parent / "synthetic_data"


def _to_int(value: str) -> Optional[int]:
    value = (value or "").strip()
    if not value:
        return None
    return int(float(value))


def _to_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    # Handles both "2026-07-01" and "2026-07-01 06:12:00".
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {value!r}")


def load_salesforce_accounts(path: Optional[Path] = None) -> List[SalesforceAccount]:
    path = path or (DATA_DIR / "salesforce_accounts.csv")
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                SalesforceAccount(
                    sfdc_account_id=row["sfdc_account_id"].strip(),
                    account_name=row["account_name"].strip(),
                    customer_key=row["customer_key"].strip(),
                    region=row["region"].strip(),
                    pricing_tier=row["pricing_tier"].strip(),
                    last_quoted_audience_count=_to_int(row["last_quoted_audience_count"]),
                    last_quote_date=_to_date(row["last_quote_date"]),
                    renewal_date=_to_date(row["renewal_date"]),
                    account_notes=row.get("account_notes", "").strip(),
                )
            )
    return out


def load_dbx_current(path: Optional[Path] = None) -> List[DbxCurrent]:
    path = path or (DATA_DIR / "databricks_audience_current.csv")
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                DbxCurrent(
                    databricks_record_id=row["databricks_record_id"].strip(),
                    customer_key=row["customer_key"].strip(),
                    business_unit=row["business_unit"].strip(),
                    audience_count=_to_int(row["audience_count"]),
                    last_refreshed_at=_to_date(row["last_refreshed_at"]),
                )
            )
    return out


def load_dbx_history(path: Optional[Path] = None) -> List[DbxHistory]:
    path = path or (DATA_DIR / "databricks_audience_history.csv")
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                DbxHistory(
                    customer_key=row["customer_key"].strip(),
                    business_unit=row["business_unit"].strip(),
                    snapshot_date=_to_date(row["snapshot_date"]),
                    audience_count=_to_int(row["audience_count"]),
                )
            )
    return out
