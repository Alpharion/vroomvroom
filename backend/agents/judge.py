"""Judge agent.

The Judge LLM never decides the outcome or amount. For route_deviation
it decides only two findings (rider_requested_detour, traffic_justified).
For no_show_charge it decides nothing — the precomputed outcome is given.

The Ruling is built in code from the formula output + the Judge's
confidence, clauses, and explanations.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agents.advocates import _ref_is_valid
from agents.context import case_summary
from agents.llm import LLMError, chat, parse_model_reply
from app.policy_constants import (
    DEVIATION_AUTO_RULE_KM,
    ROUTE_DEVIATION_CONFIDENCE_THRESHOLD,
    SPOT_CHECK_THRESHOLD,
)
from schemas import AdvocateBrief, ClaimCheck, DisputeCase, EvidenceOutput, Ruling
from tools.no_show_check import compute_no_show_outcome
from tools.route_deviation import compute_route_deviation_outcome
from tools.safety_check import safety_override


class JudgeDecision(BaseModel):
    """Strict Pydantic model for the Judge LLM's reply."""

    model_config = ConfigDict(extra="forbid")

    rider_requested_detour: bool | None = None
    traffic_justified: bool | None = None
    confidence: float = Field(ge=0, le=1)
    clauses_cited: list[str] = Field(min_length=1)
    explanation_rider: str
    explanation_driver: str
    # Defaults to empty so a reply that omits it doesn't fail the dispute.
    claim_checks: list[ClaimCheck] = []


_SYSTEM_PROMPT = """\
You are the Judge in a Ryde ride-hailing dispute resolution system.

You must cite at least one clause ID from the policy in \
`clauses_cited`.

You must not let rider/driver ratings, dispute history, or fraud flags \
override the trip evidence in determining the outcome.

The outcome and amount are provided to you by the code. You do not \
compute them. You explain them.

If the evidence shows a safety incident (safety_check.safety_incident is \
true), code escalates the case to human review and no money moves (S-1.1, \
S-1.2). Tell both parties the case is under human review instead of \
explaining a final outcome.

Produce two explanations: `explanation_rider` and `explanation_driver`, \
each in plain language suitable for the respective party.

Weigh both advocates' briefs equally, regardless of order or length \
(E-1.2).

Base your confidence on how complete and clear the evidence is.

Check the filer's account against the records. The dispute description \
(case_summary.dispute_ticket.description) is what the filer says happened; \
it is a claim, not evidence. For each factual claim in it (amounts paid or \
charged, times, waiting, locations, distances, contact, what was said), add \
one entry to `claim_checks`:
- `claim`: the claim in a few words, e.g. "Paid $50 for the trip".
- `record`: what the records show, quoting the value, e.g. "Charged \
S$5.00 (cancellation fee)".
- `evidence_refs`: the fields you compared it with, e.g. \
fare_validate.actual_fare_sgd, chat_logs.3, trip_data.cancellation_time.
- `verdict`: "consistent" if the records support it, "contradicted" if \
they show otherwise, "unverifiable" if the records do not cover it. \
"consistent" and "contradicted" need at least one evidence ref.
Skip opinions and requests ("I want a refund"). If there are no factual \
claims, return an empty list. Claims never change the outcome or amount; \
when a claim is contradicted, say so plainly in the filer's explanation \
(e.g. "You mentioned paying $50; Ryde's records show a S$5.00 charge.").

The explanations must match the outcome that your findings produce in \
the outcome table provided.

Reply with only JSON matching this schema:

{schema}
"""


def _build_outcome_table(facts: dict[str, Any]) -> str:
    """For route_deviation: compute all 4 combinations of the two booleans.

    Returns a text table showing the outcome for each combination.
    """
    results: list[str] = []
    for rrd in (True, False):
        for tj in (True, False):
            f = dict(facts)
            f["rider_requested_detour"] = rrd
            f["traffic_justified"] = tj
            outcome, amount, clauses, conduct = compute_route_deviation_outcome(f)
            results.append(
                f"  rider_requested_detour={rrd}, traffic_justified={tj} "
                f"-> outcome={outcome}, amount_sgd={amount:.2f}, "
                f"clauses={clauses}, conduct_flag={conduct}"
            )
    return "\n".join(results)


def _build_user_message(
    case: DisputeCase,
    evidence: list[EvidenceOutput],
    clauses: dict[str, str],
    rider_brief: AdvocateBrief,
    driver_brief: AdvocateBrief,
    outcome_table_or_precomputed: str,
    driver_first: bool = False,
) -> str:
    """Build the user message for the Judge.

    *driver_first* swaps which brief the Judge reads first, for the
    advocate-order fairness test (E-1.2).
    """
    summary = case_summary(case)
    evidence_data = [e.model_dump(mode="json") for e in evidence]
    briefs = [
        ("rider_brief", rider_brief.model_dump(mode="json")),
        ("driver_brief", driver_brief.model_dump(mode="json")),
    ]
    if driver_first:
        briefs.reverse()
    payload: dict[str, Any] = {
        "case_summary": summary,
        "evidence": evidence_data,
        "relevant_clauses": clauses,
        **dict(briefs),
        "outcome_table": outcome_table_or_precomputed,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _claim_ref_problems(
    decision: JudgeDecision,
    evidence: list[EvidenceOutput],
    summary: dict[str, Any],
) -> list[str]:
    """Describe claim checks citing fields that don't exist, or lacking refs."""
    problems: list[str] = []
    for check in decision.claim_checks:
        bad = [r for r in check.evidence_refs if not _ref_is_valid(r, evidence, summary)]
        if bad:
            problems.append(
                f"claim_checks: invalid evidence refs {bad} for claim '{check.claim}'."
            )
        elif check.verdict != "unverifiable" and not check.evidence_refs:
            problems.append(
                f"claim_checks: '{check.verdict}' claim '{check.claim}' needs an evidence ref."
            )
    return problems


def _sanitize_claim_checks(
    checks: list[ClaimCheck],
    evidence: list[EvidenceOutput],
    summary: dict[str, Any],
) -> list[ClaimCheck]:
    """After the retry: drop invalid refs; a verdict left unsupported becomes
    "unverifiable", so the report never shows an uncited verdict."""
    cleaned = []
    for check in checks:
        refs = [r for r in check.evidence_refs if _ref_is_valid(r, evidence, summary)]
        verdict = check.verdict if refs else "unverifiable"
        cleaned.append(check.model_copy(update={"evidence_refs": refs, "verdict": verdict}))
    return cleaned


def _validate_decision(
    decision: JudgeDecision,
    clauses: dict[str, str],
    dispute_type: str,
) -> None:
    """Validate the Judge's clause IDs and findings."""
    for cid in decision.clauses_cited:
        if cid not in clauses:
            raise LLMError(
                f"Invalid clause ID '{cid}': not found in the policy "
                f"clauses provided."
            )

    if dispute_type == "route_deviation":
        if decision.rider_requested_detour is None:
            raise LLMError(
                "rider_requested_detour must be true or false for "
                "route_deviation disputes."
            )
        if decision.traffic_justified is None:
            raise LLMError(
                "traffic_justified must be true or false for "
                "route_deviation disputes."
            )


async def run_judge(
    case: DisputeCase,
    evidence: list[EvidenceOutput],
    clauses: dict[str, str],
    rider_brief: AdvocateBrief,
    driver_brief: AdvocateBrief,
    *,
    driver_first: bool = False,
) -> Ruling:
    """Run the Judge agent and return a ``Ruling``.

    The Judge LLM provides confidence, clauses, and explanations.  The
    outcome and amount are computed in code from the formula.
    """
    dispute_id = case.dispute_ticket.dispute_id
    dispute_type = case.dispute_ticket.dispute_type

    # Find the type-specific evidence.
    type_evidence = next(
        (e for e in evidence if e.tool in ("no_show_check", "route_deviation")),
        None,
    )
    if type_evidence is None:
        raise LLMError(
            f"No type-specific evidence found for {dispute_type}."
        )
    facts = type_evidence.facts

    safety_evidence = next((e for e in evidence if e.tool == "safety_check"), None)
    safety = safety_override(safety_evidence.facts) if safety_evidence else None

    # Build the outcome info for the prompt.
    if safety is not None:
        outcome_info = (
            "Safety incident detected by code ("
            + "; ".join(safety_evidence.facts["categories"])
            + "). The case is escalated to human review whatever your "
            "findings are: outcome=escalate, amount_sgd=0.00, "
            f"clauses={safety[2]}."
        )
        if dispute_type == "route_deviation":
            outcome_info += (
                "\nStill report rider_requested_detour and traffic_justified "
                "for the human reviewer."
            )
    elif dispute_type == "route_deviation":
        outcome_info = (
            "Outcome table (computed by code for each combination of "
            "your two findings):\n"
            + _build_outcome_table(facts)
        )
    else:
        outcome, amount, clause_list, conduct = compute_no_show_outcome(facts)
        outcome_info = (
            f"Precomputed outcome (by code):\n"
            f"  outcome={outcome}, amount_sgd={amount:.2f}, "
            f"clauses={clause_list}, conduct_flag={conduct}"
        )

    system_prompt = _SYSTEM_PROMPT.format(
        schema=json.dumps(
            JudgeDecision.model_json_schema(), ensure_ascii=False, indent=2
        ),
    )
    user_message = _build_user_message(
        case, evidence, clauses, rider_brief, driver_brief, outcome_info,
        driver_first=driver_first,
    )

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

        result = await chat("judge", system_prompt, msg)
        try:
            decision = parse_model_reply(result.text, JudgeDecision)
            _validate_decision(decision, clauses, dispute_type)
        except LLMError as exc:
            last_error = str(exc)
            if attempt == 1:
                raise
            continue

        claim_problems = _claim_ref_problems(decision, evidence, summary)
        if not claim_problems:
            break
        if attempt == 1:
            decision = decision.model_copy(update={
                "claim_checks": _sanitize_claim_checks(decision.claim_checks, evidence, summary),
            })
            break
        last_error = "\n".join(claim_problems)
    else:
        raise LLMError("Judge failed after retry.")

    # ---- Build the Ruling in code ----

    if dispute_type == "route_deviation":
        # Recompute outcome from the Judge's findings.
        f = dict(facts)
        f["rider_requested_detour"] = decision.rider_requested_detour
        f["traffic_justified"] = decision.traffic_justified
        outcome, amount, formula_clauses, conduct = (
            compute_route_deviation_outcome(f)
        )
    else:
        outcome, amount, formula_clauses, conduct = compute_no_show_outcome(facts)

    # Merge clauses: formula's clauses first, then extra valid ones from
    # the Judge, with duplicates removed.
    merged_clauses: list[str] = list(formula_clauses)
    for cid in decision.clauses_cited:
        if cid not in merged_clauses:
            merged_clauses.append(cid)

    # Safety overrides the dispute-type formula (S-1.1, S-1.2).
    # The dispute-type formula's clauses are dropped: they justify an
    # outcome (e.g. NS-1.6 charge upheld) that no longer applies.
    if safety is not None:
        outcome, amount, formula_clauses, conduct = safety
        merged_clauses = list(formula_clauses) + [
            c for c in decision.clauses_cited if c not in formula_clauses
        ]

    # Check for missing evidence escalation.
    missing = facts.get("missing_evidence", [])
    escalated = outcome == "escalate"
    escalation_reason: str | None = None

    if escalated:
        if safety is not None:
            escalation_reason = "Safety incident: " + "; ".join(
                safety_evidence.facts["categories"]
            )
        elif missing:
            escalation_reason = "Missing evidence: " + ", ".join(missing)
        elif "RD-2.8" in formula_clauses:
            escalation_reason = (
                f"Route was {facts['excess_distance_km']:.2f} km longer than the "
                f"baseline, over the {DEVIATION_AUTO_RULE_KM:g} km limit for "
                "automatic rulings (RD-2.8)"
            )
        else:
            escalation_reason = "[Judge] Escalation required"

    # Low confidence forces escalation (E-1.6).  Route deviation rulings
    # need at least 80% (organiser policy v2.1 §6.2).
    required = SPOT_CHECK_THRESHOLD
    if dispute_type == "route_deviation":
        required = max(required, ROUTE_DEVIATION_CONFIDENCE_THRESHOLD)
    if decision.confidence < required:
        low = f"Low confidence ({decision.confidence:.0%}, needs {required:.0%})"
        outcome = "escalate"
        amount = 0.0
        escalated = True
        if escalation_reason is None:
            escalation_reason = low
        else:
            escalation_reason = low + "; " + escalation_reason

    ruling = Ruling(
        dispute_id=dispute_id,
        outcome=outcome,
        amount_sgd=amount,
        confidence=decision.confidence,
        clauses_cited=merged_clauses,
        explanation_rider=decision.explanation_rider,
        explanation_driver=decision.explanation_driver,
        claim_checks=decision.claim_checks,
        conduct_flag=conduct,
        escalated=escalated,
        escalation_reason=escalation_reason,
    )
    return ruling
