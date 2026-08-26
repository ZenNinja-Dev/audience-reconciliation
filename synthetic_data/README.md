# Synthetic data

This folder is a **fabricated** dataset for a portfolio demonstration. Nothing here
is real customer data — all company names, keys, and numbers are invented. It stands
in for two systems a B2B SaaS vendor ("Meridian", fictional) would have: a CRM
(Salesforce) where Sales builds quotes, and a data warehouse (Databricks) that holds
the live audience numbers pricing is based on.

It is deliberately **not perfectly clean** — it reflects the kind of messy reality a
reconciliation tool has to survive: accounts that don't join cleanly, stale rows, a
value worth double-checking before trusting, and keys that are shared or drifted.

## Files

### `salesforce_accounts.csv`
One row per CRM account — what Sales sees when building a quote.

| Column | Description |
|---|---|
| `sfdc_account_id` | Salesforce account ID (18-char style) |
| `account_name` | Account display name |
| `customer_key` | The field Sales Ops believes joins into the warehouse |
| `region` | NA / EMEA / APAC / Global |
| `pricing_tier` | Current pricing tier |
| `last_quoted_audience_count` | The audience number on the account's most recent quote |
| `last_quote_date` | Date that quote was built |
| `renewal_date` | Contract renewal date |
| `account_notes` | Freeform notes a rep or sales-ops person logged (not always populated) |

### `databricks_audience_current.csv`
A snapshot of what a warehouse (Databricks/Genie) query for "current audience count"
returns, as of `2026-07-01`.

| Column | Description |
|---|---|
| `databricks_record_id` | Internal warehouse record ID |
| `customer_key` | The key on the warehouse side |
| `business_unit` | Business unit the record is scoped to |
| `audience_count` | Audience count for that business unit |
| `last_refreshed_at` | When this record was last updated |

Note: not every CRM account has a matching row here, and some accounts have more than one.

### `databricks_audience_history.csv`
Weekly snapshots of the same data going back three weeks, where history is available.
Lets the solution reason about trend and flag an implausible change rather than
trusting a single point-in-time number.

## What this stands in for
- `salesforce_accounts.csv` ≈ a Salesforce report / API pull
- `databricks_audience_*.csv` ≈ what a Databricks Genie query would return for
  "current audience count by account"

You can load these as CSVs, drop them in SQLite/DuckDB, or treat them as an API
payload — whatever the architecture calls for. If the design uses a natural-language
(Genie-style) query layer, that layer can be simulated calling into this data rather
than standing up real infrastructure.
