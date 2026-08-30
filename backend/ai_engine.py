"""
Groq-powered deal classification (free tier, GPT-OSS-120B). Every deal gets
sent to the model with its own numbers (days in stage, days since contact)
alongside the pipeline's actual historical average for that stage, pulled
from Postgres - that comparison against real history is what keeps the
signal grounded instead of being a generic guess.

If the Groq call fails (rate limit, bad key, outage), a rule-based fallback
still classifies the deal so one bad API call doesn't stop the whole sync.
"""

import json
import os
import re

from groq import Groq

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


SYSTEM_PROMPT = (
    "You are a sales operations analyst. Given one CRM deal's state and how "
    "it compares to similar deals, classify its health and explain why in "
    "one sentence. Respond with ONLY a JSON object of the exact shape "
    '{"signal": "at_risk" | "stalling" | "on_track", "reason": "<one sentence>"}. '
    "No markdown, no code fences, no extra text before or after the JSON."
)


def classify_deal(
    deal_name: str,
    stage_label: str,
    days_in_stage: int,
    days_since_contact: int | None,
    avg_days_in_stage: float,
    amount: float | None,
) -> dict:
    contact_line = f"{days_since_contact} days ago" if days_since_contact is not None else "no recorded contact activity"
    amount_line = f"${amount:,.0f}" if amount else "unknown"

    prompt = (
        f"Deal: {deal_name}\n"
        f"Current stage: {stage_label}\n"
        f"Days in current stage: {days_in_stage}\n"
        f"Last contact activity: {contact_line}\n"
        f"Average days other deals spend in this stage: {avg_days_in_stage:.1f}\n"
        f"Deal amount: {amount_line}\n\n"
        "Classify this deal's health as at_risk, stalling, or on_track, and "
        "give one specific, concrete reason grounded in the numbers above - "
        "reference the actual day counts, don't just restate the label."
    )

    try:
        response = _get_client().chat.completions.create(
            model=MODEL,
            max_tokens=300,
            temperature=0.2,
            reasoning_effort="low",  # gpt-oss is a reasoning model - without this,
            # it burns most of max_tokens on hidden reasoning before ever
            # emitting the JSON answer, truncating it mid-response
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        return _parse_response(text)
    except Exception as exc:  # Groq unavailable shouldn't stop the sync
        return _fallback_classify(days_in_stage, days_since_contact, avg_days_in_stage, error=str(exc))


def _parse_response(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in Groq response: {text!r}")

    parsed = json.loads(match.group(0))
    signal = parsed.get("signal")
    if signal not in {"at_risk", "stalling", "on_track"}:
        raise ValueError(f"Unexpected signal value: {signal!r}")

    return {"signal": signal, "reason": (parsed.get("reason") or "").strip() or "No reason provided."}


def _fallback_classify(
    days_in_stage: int,
    days_since_contact: int | None,
    avg_days_in_stage: float,
    error: str,
) -> dict:
    """Simple rule-based backup used only when the Groq call itself fails."""
    stalled_contact = days_since_contact is None or days_since_contact > 10
    over_average = days_in_stage > avg_days_in_stage * 1.5

    if over_average and stalled_contact:
        signal = "at_risk"
        reason = f"Stuck {days_in_stage}d in stage (avg {avg_days_in_stage:.0f}d) with no recent contact."
    elif over_average or stalled_contact:
        signal = "stalling"
        reason = f"Slower than the {avg_days_in_stage:.0f}d average for this stage, or engagement has cooled."
    else:
        signal = "on_track"
        reason = f"Moving at a healthy pace ({days_in_stage}d vs {avg_days_in_stage:.0f}d average) with recent contact."

    return {"signal": signal, "reason": f"{reason} (rule-based fallback - Groq call failed: {error[:80]})"}
