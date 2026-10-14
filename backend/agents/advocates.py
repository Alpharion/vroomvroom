"""Advocate agents (Rider Advocate and Driver Advocate).

Both sides use the same system-prompt template with only the side name
filled in.  Each advocate receives the same user message (case summary +
evidence + clause texts) and must reply with JSON matching the
``AdvocateBrief`` schema.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from agents.llm import LLMError, chat, parse_model_reply
from agents.context import case_summary
from schemas import AdvocateBrief, DisputeCase, EvidenceOutput
from schemas.models import MAX_ARGUMENTS, MAX_POINT_CHARS

_AGENT_NAME = "{side}_advocate"

_SYSTEM_PROMPT = """\
You are the {side} advocate in a Ryde ride-hailing dispute resolution system.

You argue for the {side}, honestly. Use only the evidence given; never \
invent facts.

When you state a fact from the evidence, quote its value exactly as the \
evidence gives it, and cite the field it comes from. The dispute \
description is the filer's own claim, not evidence: if you rely on it, \
say so ("the rider states ..."), and never cite a tool field for it.

Every argument must cite at least one evidence ref and at least one \
clause ID from the policy given. An evidence ref is either a tool fact, \
<tool>.<fact_key> (e.g. no_show_check.total_wait_min), or a field of the \
case summary, e.g. chat_logs.3 (the 4th chat message, counting from 0), \
app_events.7 or trip_data.fare_breakdown.

At most 5 arguments, each under 400 characters; position under 200 \
characters.

List the weaknesses in your side's case in weaknesses_acknowledged.

Ratings and history may not override trip evidence (E-1.4).

Reply with only JSON matching the AdvocateBrief schema:

{schema}
"""


def _build_user_message(
    case: DisputeCase,
    evidence: list[EvidenceOutput],
    clauses: dict[str, str],
) -> str:
    """Build the identical user message for both advocates."""
    summary = case_summary(case)
    evidence_data = [e.model_dump(mode="json") for e in evidence]
    payload: dict[str, Any] = {
        "case_summary": summary,
        "evidence": evidence_data,
        "relevant_clauses": clauses,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


_MAX_POSITION_CHARS = AdvocateBrief.model_fields["position"].metadata[0].max_length


def _shorten(text: str, limit: int) -> str:
    """Cut *text* to *limit* characters at a word boundary, ending in an ellipsis."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "…"


def _fit_to_caps(text: str) -> str:
    """Trim an over-long reply to the brief's length caps.

    Used only after the retry is also too long: the caps keep both sides
    equal (E-1.2), and one long sentence should not fail the dispute.
    Returns the reply unchanged if it is not a JSON object.
    """
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return text
    if not isinstance(data, dict):
        return text
    if isinstance(data.get("position"), str):
        data["position"] = _shorten(data["position"], _MAX_POSITION_CHARS)
    if isinstance(data.get("arguments"), list):
        data["arguments"] = data["arguments"][:MAX_ARGUMENTS]
        for arg in data["arguments"]:
            if isinstance(arg, dict) and isinstance(arg.get("point"), str):
                arg["point"] = _shorten(arg["point"], MAX_POINT_CHARS)
    return json.dumps(data, ensure_ascii=False)


def _drop_uncited_arguments(text: str) -> str:
    """Drop arguments that name no evidence ref or no clause, when others remain.

    An advocate sometimes makes a point from the filer's own words ("the rider states ...")
    and, as the prompt tells it not to cite a tool fact for a claim, leaves ``evidence_refs``
    empty. The schema rejects that, and one uncited point should not fail the whole dispute.
    Returns the reply unchanged if it is not a JSON object or if no argument would be left, so
    the normal validation error and retry still apply.
    """
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return text
    args = data.get("arguments") if isinstance(data, dict) else None
    if not isinstance(args, list):
        return text
    cited = [
        a for a in args
        if isinstance(a, dict) and a.get("evidence_refs") and a.get("clauses")
    ]
    if not cited or len(cited) == len(args):
        return text
    data["arguments"] = cited
    return json.dumps(data, ensure_ascii=False)


def _ref_is_valid(
    ref: str, evidence: list[EvidenceOutput], summary: dict[str, Any],
) -> bool:
    """True if *ref* names a tool fact or a case-summary field.

    Only the first two parts are checked, so nested refs like
    ``history_lookup.rider.avg_rating`` or ``app_events.7.details`` pass
    when ``history_lookup.rider`` / ``app_events.7`` exist.
    """
    parts = ref.split(".")
    if len(parts) < 2:
        return False
    head, key = parts[0], parts[1]
    for ev in evidence:
        if ev.tool == head:
            return key in ev.facts
    section = summary.get(head)
    if isinstance(section, list):
        return key.isdigit() and int(key) < len(section)
    if isinstance(section, dict):
        return key in section
    return False


def _brief_problems(
    brief: AdvocateBrief,
    evidence: list[EvidenceOutput],
    clauses: dict[str, str],
    summary: dict[str, Any],
) -> list[str]:
    """Describe every invalid evidence ref and clause ID in *brief*."""
    problems: list[str] = []
    for arg in brief.arguments:
        problems += [
            f"Invalid evidence ref '{ref}': not a tool fact or case summary field."
            for ref in arg.evidence_refs
            if not _ref_is_valid(ref, evidence, summary)
        ]
        problems += [
            f"Invalid clause ID '{cid}': not found in the policy clauses provided."
            for cid in arg.clauses
            if cid not in clauses
        ]
    return problems


def _drop_invalid(
    brief: AdvocateBrief,
    evidence: list[EvidenceOutput],
    clauses: dict[str, str],
    summary: dict[str, Any],
) -> AdvocateBrief:
    """Remove invalid refs and clauses after the retry also failed.

    One bad citation should not fail the whole dispute.  Arguments left
    without a valid ref or clause are dropped; if none remain, raise.
    """
    kept = []
    for arg in brief.arguments:
        refs = [r for r in arg.evidence_refs if _ref_is_valid(r, evidence, summary)]
        cids = [c for c in arg.clauses if c in clauses]
        if refs and cids:
            kept.append(arg.model_copy(update={"evidence_refs": refs, "clauses": cids}))
    if not kept:
        raise LLMError(f"Advocate {brief.side}: no argument has a valid citation.")
    return brief.model_copy(update={"arguments": kept})


async def run_advocate(
    side: Literal["rider", "driver"],
    case: DisputeCase,
    evidence: list[EvidenceOutput],
    clauses: dict[str, str],
) -> AdvocateBrief:
    """Run one advocate agent and return its brief.

    *side* is "rider" or "driver".  The advocate calls the LLM, parses
    the reply into an ``AdvocateBrief``, validates evidence refs and
    clause IDs, and retries once on failure before raising ``LLMError``.
    """
    agent = _AGENT_NAME.format(side=side)
    system_prompt = _SYSTEM_PROMPT.format(
        side=side,
        schema=json.dumps(
            AdvocateBrief.model_json_schema(), ensure_ascii=False, indent=2
        ),
    )
    user_message = _build_user_message(case, evidence, clauses)
    summary = case_summary(case)

    last_error: str | None = None
    for attempt in range(2):
        msg = user_message
        if last_error is not None:
            msg = (
                user_message
                + "\n\nYour previous reply had an error:\n"
                + last_error
                + "\nPlease fix the error and reply again with valid JSON."
            )

        result = await chat(agent, system_prompt, msg)
        text = _fit_to_caps(result.text) if attempt == 1 else result.text
        text = _drop_uncited_arguments(text)
        try:
            brief = parse_model_reply(text, AdvocateBrief)
            # Override side and dispute_id to ensure consistency.
            brief = brief.model_copy(update={
                "side": side,
                "dispute_id": case.dispute_ticket.dispute_id,
            })
        except LLMError as exc:
            last_error = str(exc)
            if attempt == 1:
                raise
            continue

        problems = _brief_problems(brief, evidence, clauses, summary)
        if not problems:
            return brief
        if attempt == 1:
            return _drop_invalid(brief, evidence, clauses, summary)
        last_error = "\n".join(problems)

    # Unreachable — the loop either returns or raises.
    raise LLMError(f"Advocate {side} failed after retry.")
