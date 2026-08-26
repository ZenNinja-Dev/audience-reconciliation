# Eval set — expected trouble, actual behaviour, pass/fail

This is the reasoning behind `eval_cases.json`. Before writing the engine I went
through the synthetic dataset by hand and wrote down which accounts I expected to be
trouble and why. The engine is then asserted against those expectations by
`python -m eval.run_eval` (currently **12/12 pass**).

The point of the exercise is not that every account resolves — it is that the messy
ones are *caught and routed to a human* instead of silently producing a wrong price.

## What I expected trouble from, and what happened

| Account | Key | Why I expected trouble | Expected verdict | Actual | Pass |
|---|---|---|---|---|---|
| Larkspur Retail Co | ACC-2001 | Quote from April, live number has since grown | REFRESH (safe) | REFRESH/HIGH | ✅ |
| Vantage Apparel Group | ACC-2002 | Control case — quote already equals live | MATCH (safe) | MATCH/HIGH | ✅ |
| Cobalt Financial | ACC-2003 | Small drift below live | REFRESH (safe) | REFRESH/HIGH | ✅ |
| Solaris Global Holdings | ACC-2004 | Quoted as ONE combined figure; warehouse has 3 BU rows → must **sum** to 542,600 | REFRESH (safe) | REFRESH/HIGH | ✅ |
| Everpeak Brands | ACC-2005 | New logo, sync maybe incomplete → **no warehouse row** | HOLD_NO_MATCH | HOLD_NO_MATCH/NONE | ✅ |
| Halcyon Media Group | ACC-2006 | Warehouse last refreshed 2026-05-08 → **54 days stale** | REVIEW_STALE | REVIEW_STALE/LOW | ✅ |
| Torch Digital | ACC-2007 | History 9,100→9,600→**486,200**: ~50x jump, almost certainly a data error | REVIEW_IMPLAUSIBLE | REVIEW_IMPLAUSIBLE/LOW | ✅ |
| Juniper CPG | ACC-2008 | SFDC key `ACC-2008` vs warehouse `ACC-2008-OLD` after rebrand → alias, confirm before trust | REFRESH/MEDIUM (not auto-safe) | REFRESH/MEDIUM | ✅ |
| Sable Industries | ACC-2009 | Shares key with Sable Analytics; one 'Combined Legacy' warehouse row → cannot attribute | ESCALATE_AMBIGUOUS | ESCALATE_AMBIGUOUS/NONE | ✅ |
| Sable Analytics | ACC-2009 | Other half of the shared key | ESCALATE_AMBIGUOUS | ESCALATE_AMBIGUOUS/NONE | ✅ |
| Ridgeline Solutions | ACC-2010 | Quote equals live; pending tier upgrade is a pricing note, **not** an audience issue → must not affect verdict | MATCH (safe) | MATCH/HIGH | ✅ |
| Aperture Consumer Tech | ACC-2011 | Large account, quote a few % below live | REFRESH (safe) | REFRESH/HIGH | ✅ |

Net result: **6 accounts safe to auto-use, 6 correctly held for a human.** No account
with dirty data was handed back a "trustworthy" number.

## The found-and-fixed failure

**Account:** Torch Digital (ACC-2007).

**The failure.** In the first working version of the engine, reconciliation was
mapping → aggregation → quote-drift comparison, with no trend check. Torch's current
warehouse value is 486,200. The quote was 9,400. The engine computed a +5,072% drift
and returned **REFRESH — update the quote to 486,200, confidence HIGH, safe to send.**
That is the worst possible outcome: it would have taken an obvious data-pipeline glitch
and written it straight into a customer's price, with a green "safe" flag on it.

I caught it because I had pre-registered Torch as an expected-trouble account (the
history file exists precisely to reason about trend), so the eval failed: expected
REVIEW_IMPLAUSIBLE, got REFRESH.

**The fix.** Added `ReconciliationEngine._plausibility()` (engine.py, Step 5): a
deterministic week-over-week check against `databricks_audience_history.csv`. Any
business unit whose latest step exceeds `IMPLAUSIBLE_WOW_PCT` (300%) is flagged; the
account short-circuits to REVIEW_IMPLAUSIBLE, `reconciled_count` is set to `None` (the
engine refuses to hand back a number it does not trust), and the action tells the rep
the last trusted value (9,600) and to route it to the data team. Precedence was set so
plausibility and staleness are evaluated **before** the quote-drift comparison — an
untrustworthy number never reaches the "looks like a refresh" branch.

Re-ran the eval: Torch now passes, and the 11 other cases were unaffected.

**The second, related fix (prompt layer).** The same class of error showed up in the
AI narration prompt. See `prompts/CHANGELOG.md`: v1 asked the model to work out the
correct count from raw rows, and on Torch it "explained" the 486,200 as real and told
the rep to quote it. v2 removes the count from the model entirely — it may only
rephrase the engine's already-decided verdict. Counting is a rules problem before it
is ever an AI problem, and this is where that principle earned its place.

## What I would add next with another day
- A statistical plausibility check (rolling z-score / MAD) instead of a single fixed
  WoW threshold, so slow-drift anomalies are caught too, not just spikes.
- Per-business-unit freshness surfacing when only *some* BUs of a multi-BU account are
  stale (today the whole account inherits the oldest row's age).
- A regression snapshot test that pins the full JSON output so any accidental change in
  a verdict fails CI loudly.
