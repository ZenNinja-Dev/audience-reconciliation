"""
The (bounded) AI layer.

The engine has already decided the number, the status and the confidence. This
layer does exactly one non-deterministic thing: turn that structured verdict
into a short, plain-language explanation a salesperson or a reviewer can read.

Design choices that matter:
  * The LLM is OPTIONAL and PLUGGABLE. With no provider configured, a
    deterministic template produces the explanation, so the prototype runs
    end-to-end on any machine with zero dependencies and zero API keys.
  * The prompt is a VERSIONED ARTIFACT on disk (prompts/…). We load it here so
    the exact text sent to a model is reviewable and diffable, not hidden in a
    string literal.
  * The AI is never trusted with the count. If a provider is configured we still
    pass the engine's number/status in; the model may only rephrase, never
    recompute. This is the "counting is a rules problem before an AI problem"
    principle enforced in code.
"""

import os
from pathlib import Path
from typing import Optional

from .models import ReconResult, Status

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
ACTIVE_PROMPT = PROMPT_DIR / "explain_discrepancy_v2.md"


# --------------------------------------------------------------------------- #
# Pluggable provider
# --------------------------------------------------------------------------- #
def _get_provider():
    """
    Return a callable(system_prompt, user_prompt) -> str, or None.

    Wired to be swapped for Claude / Gemini / a local Ollama model by setting
    RECON_LLM_PROVIDER. Left unset by default so the prototype is fully
    reproducible offline. Providers are imported lazily so their SDKs are never
    a hard dependency.
    """
    provider = os.environ.get("RECON_LLM_PROVIDER", "").lower().strip()
    if not provider:
        return None

    if provider == "ollama":
        def _call(system: str, user: str) -> str:
            import json
            import urllib.request

            model = os.environ.get("RECON_LLM_MODEL", "llama3.2")
            payload = json.dumps({
                "model": model,
                "prompt": f"{system}\n\n{user}",
                "stream": False,
                "options": {"temperature": 0.2},
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["response"].strip()
        return _call

    if provider == "anthropic":
        def _call(system: str, user: str) -> str:
            import anthropic  # pip install anthropic
            client = anthropic.Anthropic()
            model = os.environ.get("RECON_LLM_MODEL", "claude-3-5-haiku-latest")
            msg = client.messages.create(
                model=model, max_tokens=300, temperature=0.2,
                system=system, messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text.strip()
        return _call

    raise ValueError(f"Unknown RECON_LLM_PROVIDER: {provider!r}")


# --------------------------------------------------------------------------- #
# Prompt assembly (uses the versioned artifact on disk)
# --------------------------------------------------------------------------- #
def build_prompt(res: ReconResult) -> str:
    template = ACTIVE_PROMPT.read_text(encoding="utf-8")
    facts = (
        f"account_name: {res.account_name}\n"
        f"status: {res.status.value}\n"
        f"confidence: {res.confidence.value}\n"
        f"quoted_count: {res.quoted_count}\n"
        f"reconciled_count: {res.reconciled_count}\n"
        f"drift_pct: {res.drift_pct}\n"
        f"matched_dbx_key: {res.matched_dbx_key}\n"
        f"business_unit_breakdown: {res.business_unit_breakdown}\n"
        f"data_age_days: {res.data_age_days}\n"
        f"reason_codes: {res.reasons}\n"
        f"engine_action_required: {res.action_required}\n"
    )
    return template.replace("{{FACTS}}", facts)


SYSTEM_PROMPT = (
    "You explain an Audience-count reconciliation verdict to a salesperson in at "
    "most two sentences. You must not invent, recompute, or change any number, "
    "status, or confidence — only rephrase the facts you are given. If the status "
    "is not MATCH or REFRESH, make clear the number is not safe to quote yet."
)


# --------------------------------------------------------------------------- #
# Deterministic fallback (no LLM)
# --------------------------------------------------------------------------- #
def _template_explanation(res: ReconResult) -> str:
    n = f"{res.reconciled_count:,}" if res.reconciled_count is not None else "n/a"
    q = f"{res.quoted_count:,}" if res.quoted_count is not None else "n/a"

    if res.status == Status.MATCH:
        return (
            f"The quoted Audience of {q} matches the current Databricks number. "
            f"Safe to send."
        )
    if res.status == Status.REFRESH:
        bu = ""
        if len(res.business_unit_breakdown) > 1:
            parts = ", ".join(f"{k} {v:,}" for k, v in res.business_unit_breakdown.items())
            bu = f" (summed across business units: {parts})"
        return (
            f"Current Audience is {n}{bu}, versus {q} on the last quote. "
            f"Update the quote to {n} before sending."
        )
    if res.status == Status.REVIEW_STALE:
        return (
            f"The best available Audience is {n}, but the Databricks data is "
            f"{res.data_age_days} days old, so it is not confirmed current. "
            f"Verify or refresh before quoting."
        )
    if res.status == Status.REVIEW_IMPLAUSIBLE:
        return (
            "The current Databricks Audience jumped implausibly week-over-week and "
            "is likely a data error, so no number is offered. Route to the data "
            "team before quoting."
        )
    if res.status == Status.HOLD_NO_MATCH:
        return (
            "No Databricks Audience record maps to this account, so the count "
            "cannot be validated. Confirm the sync/mapping before quoting."
        )
    if res.status == Status.ESCALATE_AMBIGUOUS:
        return (
            "This account shares a Databricks key with another account, so the "
            "Audience cannot be attributed to it alone. The data team must split "
            "the key first."
        )
    return res.action_required


def explain(res: ReconResult) -> str:
    """Return a short human-readable explanation for one verdict."""
    provider = _get_provider()
    if provider is None:
        return _template_explanation(res)
    try:
        return provider(SYSTEM_PROMPT, build_prompt(res))
    except Exception as exc:  # never let the narration layer break a run
        return _template_explanation(res) + f"  [note: LLM unavailable ({exc}); used template]"
