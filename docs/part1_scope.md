# Part 1 — Scope

*A portfolio demonstration by Jakub Lazový · reconciliation & pre-quote validation*

**Scenario (fictional).** A B2B SaaS vendor ("Meridian") has moved to a pricing model
where a contract's price is tied to the customer's **audience count** per account.
Sales keeps quoting stale or wrong numbers, causing pricing errors and rework. In a
leadership meeting someone says: *"We should have AI pull this from the warehouse and
keep it current by account."* That one sentence is the whole brief — which mirrors how
real requests actually arrive.

Below are the questions I'd take back to the business, the assumptions I make instead
to build a standalone prototype, how I'd measure success, and what I'd leave out of a
v1.

## Clarifying questions I'd take back to the business

**On the definition of the number.** What does "audience count" mean under the pricing
rules — one number per account, or per business unit / region that then rolls up? When
an account has multiple warehouse rows (Solaris has three), is the contract figure the
sum, the largest, or a specific unit? Is pricing tied to a point-in-time value or an
average over the term? These aren't edge cases — they change what "correct" means, and
counting is a rules problem before it is an AI problem.

**On the mapping.** Is the CRM `customer_key` a reliable join into the warehouse, and
who owns it when it drifts (Juniper's key is `ACC-2008` in the CRM but `ACC-2008-OLD`
in the warehouse after a rebrand)? What is the source of truth when one key maps to
several accounts, or several accounts share one key (Sable Industries and Sable
Analytics share `ACC-2009`)? Is there a maintained mapping table, or is this tribal
knowledge in Sales Ops' heads today?

**On freshness and trust.** How current must the number be to be quotable — minutes, a
day, a week? How is the warehouse itself refreshed, and how would a rep know a value is
stale (Halcyon's record is 54 days old)? What is the tolerance for being wrong: is a 2%
drift acceptable, or does every unit of audience move the price?

**On today's failure.** What actually happens now when a quote goes out with a wrong
count — is it caught in deal desk, at renewal, or only when a customer disputes an
invoice? What's the cost of each wrong quote (rework hours, discount give-backs,
credibility)? That number sizes the whole project.

## Assumptions I make instead (to build a standalone prototype)

- "Audience count" = the current total across all of an account's warehouse
  business-unit rows; multi-unit accounts are **summed**. Most defensible reading of
  the data.
- `customer_key` is the intended join key but **not** guaranteed clean; known drift is
  handled by an alias/mapping rule, and unknown drift is escalated, not guessed.
- The number must be **current as of the latest warehouse refresh**; a record older
  than ~2 weeks is treated as unconfirmed.
- Wrong counts today are caught late and cause pricing rework and renewal friction —
  enough to justify a validation step, but not so catastrophic that v1 needs real-time
  streaming.
- Everything runs against a synthetic dataset; no production access is assumed.

## First-pass definition of success (what I'd track post-launch)

- **Primary:** % of quotes sent with a *validated* audience count (target: from ~0 to
  the large majority of eligible quotes).
- **Quality:** pricing-error / quote-rework rate on validated quotes vs the historical
  baseline — the metric the business actually cares about.
- **Trust/adoption:** rep adoption rate (checks per eligible quote) and override rate
  (how often a rep ignores the tool — a proxy for whether they believe it).
- **Safety:** false-confidence rate — how often the tool said "safe" and was later
  found wrong. This is the guardrail metric; it should be ~0, and any non-zero value
  pauses the rollout.

## Explicitly out of scope for v1

- Writing back into the CRM automatically (v1 recommends; a human applies).
- Real-time / streaming refresh — a daily or on-demand pull is enough.
- A polished UI — a check surfaced in the rep's existing tool is fine.
- Fixing the underlying data-quality problems in the warehouse (bad mappings, stale
  pipelines). We *detect and route* those, we don't fix the upstream data.
- Historical back-correction of already-sent quotes.
- Any account segment beyond the chosen slice (see Part 2).
