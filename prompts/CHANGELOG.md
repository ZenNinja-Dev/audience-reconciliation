# Prompt changelog

Versioned artifacts for the natural-language explanation layer. The counting
logic itself is **not** a prompt — it lives in `src/engine.py` as deterministic
rules. These versions only concern how a verdict is phrased for a human.

## v2 (active)
- **What changed:** The model is no longer allowed to compute or choose the
  Audience count. It receives the engine's already-decided `{{FACTS}}` (number,
  status, confidence, reason codes) and may only rephrase them, capped at two
  sentences, with an explicit instruction to flag any non-actionable status as
  "not safe to quote."
- **Why:** v1 asked the model to work out the correct count from raw rows. In
  testing it did exactly what you'd fear — on the ACC-2007 implausible-spike
  account it confidently "explained" the 486,200 value as real and told the rep
  to quote it, and on the ACC-2004 multi-BU account it sometimes averaged instead
  of summing. A wrong count feeds a wrong price, so the number was moved out of
  the model entirely and into tested code. This is the single most important
  change in the project.

## v1 (retired)
- First-pass prompt. Handed the model the raw quote + Databricks rows + history
  and asked it to determine the correct count and tell the rep what to use.
- Retired because it put a revenue-bearing calculation inside a non-deterministic
  component with no guardrail. Kept in the repo as `explain_discrepancy_v1.md`
  to document the reasoning.
