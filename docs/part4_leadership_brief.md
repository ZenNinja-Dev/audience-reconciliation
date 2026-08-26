# Audience Validation for Quoting — Pilot Proposal

**To:** VP of Sales · Data Governance
**From:** Data & Automation
**Re:** A pre-quote check that confirms the Audience count before it hits a contract
**Decision requested:** Approval to run a 6-week pilot with one sales segment

---

## What this does

Under the new usage-based pricing model, price is tied to each account's audience
count. Today reps pull that number from spreadsheets and stale reports, and when
it's wrong we find out late — in rework, re-quotes, and awkward renewal
conversations.

This tool gives a rep a **one-click check before they send a quote.** It pulls the
current Audience number from Databricks, reconciles it against what's on the
quote, and returns one of three things:

- **"Confirmed — safe to use"** with the number, when the data is clean and current.
- **"Update to X"** when the quote is out of date but the live number is trustworthy.
- **"Don't use this yet — here's why"** when the data is stale, missing, ambiguous,
  or looks like an error, with a clear hand-off to the data team.

In a run over the sample accounts, it cleared **half of them automatically** and
correctly **held the other half** — including one account where a data glitch had
inflated the Audience roughly fifty-fold. That number would have gone straight
into a price. The tool caught it.

## What this does NOT do

- **It does not replace the rep's judgment.** It recommends; a person still applies
  the number to the quote.
- **Reps should never treat the number as final without the tool's green light.**
  Anything short of "Confirmed — safe to use" means check before you send.
- It does not write to Salesforce, it does not fix the underlying data problems in
  Databricks (it flags them for the data team), and it does not invent a number
  when it can't find a trustworthy one — by design, it would rather say "I don't
  know" than be confidently wrong.

## How we'll judge the pilot — and the guardrail that shuts it off

- **Success metric:** a measurable drop in Audience-related pricing errors and
  quote rework in the pilot segment versus the prior period, plus reps actually
  using it (checks run per eligible quote).
- **Guardrail (kill switch):** the *false-confidence rate* — any case where the
  tool said "safe" and the number was later found wrong. Target is zero. If we see
  even a small number of these, we pause and fix before expanding. A tool that
  underpins pricing has to earn trust by never being confidently wrong, not by
  being fast.

## Rollout and adoption

1. **Start narrow:** one willing sales segment and the deal-desk / Sales Ops people
   who already own the quote-review step. They're the ones feeling the pain, so
   they're the ones who'll champion it.
2. **Earn trust in the number:** every result shows its work — where the number
   came from, how fresh it is, and why it's trusted or not. Reps move off the
   spreadsheet when they can *see* the tool is right on the accounts they know,
   not because they're told to.
3. **Handle "the AI's count doesn't match Databricks":** it shouldn't — the tool
   *reads* Databricks and never computes its own figure; the AI only writes the
   plain-English explanation. When a rep flags a mismatch, it's a real data issue
   (stale sync, wrong key mapping, a duplicate), and it routes to the data team as
   a ticket with the evidence attached. Those escalations are a feature: they're
   how we clean up the pricing data as a side effect of using it.

## The ask

Approve a 6-week pilot on one segment. We measure error/rework reduction against
the guardrail above and come back with numbers before proposing any wider rollout.
Low blast radius (recommends only, one segment, human in the loop), and it starts
surfacing bad pricing data from day one.
