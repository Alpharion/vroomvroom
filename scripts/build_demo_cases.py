"""Build the frontend's demo-mode data: one simulated hearing per case.

Run from the repo root after changing data/ or the outcome formulas:

    backend/.venv/bin/python scripts/build_demo_cases.py

For every case the evidence comes from the real evidence tools and the outcome from the real
outcome formulas (plus the safety override), so demo mode shows the same ruling the backend
would reach. Only the advocate and Judge wording is templated here instead of written by an LLM.
Output: frontend/demo_cases/<dispute_id>.json with {evidence, log, briefs, ruling}.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import _CASE_INDEX  # noqa: E402
from tools.fare_validate import fare_validate  # noqa: E402
from tools.history_lookup import history_lookup  # noqa: E402
from tools.no_show_check import compute_no_show_outcome, no_show_check  # noqa: E402
from tools.route_deviation import compute_route_deviation_outcome, route_deviation  # noqa: E402
from tools.safety_check import safety_check, safety_override  # noqa: E402

OUT = ROOT / "frontend" / "demo_cases"
CASE_IDS = ["DISP-001", "DISP-001-ORG"] + [f"TC-{n:02d}" for n in range(1, 16)] + [f"DISP-{n}" for n in range(101, 121)]


def _money(x: float) -> str:
    return f"S${x:.2f}"


def _ns_story(f: dict, outcome: str, clauses: list[str]) -> dict:
    dist, wait = f.get("driver_distance_from_pickup_m"), f.get("total_wait_min")
    msgs, calls = f.get("driver_messages", 0), f.get("driver_calls", 0)
    replies = f.get("rider_replies", 0)
    late = (f.get("arrived_minutes_vs_scheduled") or 0) > 0
    facts_line = (
        f"The driver was {dist:.0f} m from the pickup point, waited {wait:.0f} minutes, "
        f"sent {msgs} message(s) and made {calls} call(s); the rider replied {replies} time(s)."
        if dist is not None and wait is not None
        else "Key trip evidence is missing."
    )
    story = {
        "rider_pos": "The fee should be reversed: the rider says they were ready and the driver did not meet the rules for a no-show.",
        "driver_pos": "The fee stands: the driver followed every step required before cancelling.",
        "rider_args": [(facts_line, ["no_show_check.driver_distance_from_pickup_m"], ["NS-1.7"])],
        "driver_args": [(facts_line, ["no_show_check.total_wait_min", "no_show_check.contact_attempts"], ["NS-1.6"])],
        "rider_weak": "The rider has no evidence that contradicts the driver's GPS or chat record.",
        "driver_weak": "Some gates may not be met.",
    }
    if outcome == "charge_upheld":
        why = "arrived at the pickup point, waited past the free wait and the no-show threshold, and contacted the rider by message and call without a reply"
        story["rider_weak"] = "The GPS, wait time and contact record all support the driver, and the rider has nothing that contradicts them."
        story["driver_weak"] = "The driver's chat only says 'lobby area' without naming which lobby." if not late else "The driver arrived late, which counts against them but does not block the fee."
        story["exp_rider"] = f"The driver was at the pickup point, waited {wait:.0f} minutes (longer than the 5-minute free wait) and tried to reach you by message and call. The {_money(5)} no-show fee stands."
        story["exp_driver"] = f"You were at the pickup point and waited {wait:.0f} minutes, then contacted the rider by message and call. The {_money(5)} no-show fee stands in your favour."
    elif outcome == "charge_reversed":
        gate = clauses[0]
        reason = {
            "NS-1.1": ("was not at the pickup point when they said they had arrived", f"The driver's GPS arrival point was {dist:.0f} m from the pickup, outside the 10 m arrival radius."),
            "NS-1.3": ("cancelled before the 5-minute free wait was over", f"The driver waited only {wait:.0f} minutes before cancelling, less than the 5-minute free wait."),
            "NS-1.4": ("cancelled before the no-show threshold was reached", "The no-show threshold had not been reached when the driver cancelled."),
            "NS-1.5": ("did not both message and call the rider", f"The driver sent {msgs} message(s) and made {calls} call(s); the policy requires at least one of each."),
        }[gate]
        why = reason[0]
        story["rider_pos"] = f"The fee should be reversed: the driver {why}."
        story["rider_args"] = [(reason[1], ["no_show_check." + {"NS-1.1": "driver_within_arrival_radius", "NS-1.3": "free_wait_expired", "NS-1.4": "no_show_threshold_reached", "NS-1.5": "contact_requirement_met"}[gate]], [gate, "NS-1.7"])]
        story["rider_weak"] = "The rider cannot prove they were at the pickup point themselves."
        story["driver_pos"] = "The fee should stand: the driver believes they waited and tried to reach the rider."
        story["driver_args"] = [(facts_line, ["no_show_check.total_wait_min"], ["NS-1.6"])]
        story["driver_weak"] = f"The record does not meet {gate}: {reason[1][0].lower() + reason[1][1:]}"
        story["exp_rider"] = f"The driver {why}, so the no-show conditions were not met. The {_money(5)} fee is reversed and refunded to you."
        story["exp_driver"] = f"The no-show fee is reversed because you {why}. The policy needs every step met before the fee applies, so no fee is charged."
    else:  # escalate (missing evidence)
        story["exp_rider"] = story["exp_driver"] = "Important trip evidence is missing, so the system will not decide this alone. A person will review it. Nothing changes on your account until then."
    return story


def _rd_story(f: dict, outcome: str, amount: float, clauses: list[str]) -> dict:
    dev, excess = f.get("deviation_pct"), f.get("excess_distance_km")
    route_line = (
        f"The actual route was {f['actual_distance_km']:.2f} km against a {f['baseline_distance_km']:.2f} km baseline "
        f"({dev:.1f}% longer, {excess:.2f} km extra)."
        if dev is not None
        else "The route could not be rebuilt from the GPS record."
    )
    story = {
        "rider_pos": "The rider paid for a longer route than necessary and should be refunded the extra distance.",
        "driver_pos": "The driver took a route they considered reasonable and the fare should stand.",
        "rider_args": [(route_line, ["route_deviation.deviation_pct", "route_deviation.excess_distance_km"], ["RD-2.2"])],
        "driver_args": [("The rider did not ask for a different route and no traffic report is on file.", ["route_deviation.rider_requested_detour"], ["RD-2.3"])],
        "rider_weak": "A longer route alone is not enough if the rider asked for it or the fare was fixed.",
        "driver_weak": "The driver has no traffic or road-closure evidence to explain the extra distance.",
    }
    if outcome == "refund":
        story["exp_rider"] = f"The route was {dev:.0f}% longer than it should have been and you did not ask for the change. You are refunded the extra distance: {_money(amount)}."
        story["exp_driver"] = f"The route was {dev:.0f}% longer with no rider request or traffic reason, so the extra distance ({_money(amount)}) is refunded to the rider."
    elif outcome == "no_action":
        if clauses == ["RD-2.2"]:
            reason = f"The route was only {dev:.0f}% longer, under the 20% review threshold."
            story["rider_weak"] = "The difference is within normal variation for the roads taken."
        elif clauses == ["RD-2.3"]:
            reason = "You asked the driver for a different route in the chat, so the extra distance was at your request."
            story["driver_weak"] = "None of significance: the chat shows the rider asked for the detour."
        else:
            reason = f"The fare was fixed up front, so the route taken does not change the price ({dev:.0f}% longer)."
            story["driver_weak"] = "A conduct note is recorded because the longer route had no justification."
        story["exp_rider"] = f"No refund is due. {reason}"
        story["exp_driver"] = f"No refund is due. {reason}" + (" A note is kept on your record about the longer route." if f.get("fare_type") == "fixed" else "")
    else:
        missing = f.get("missing_evidence")
        if missing:
            story["exp_rider"] = story["exp_driver"] = "The GPS record is incomplete, so the route cannot be checked fairly. A person will review it. Nothing is decided against either side."
        else:
            story["exp_rider"] = story["exp_driver"] = f"The route was {excess:.1f} km longer than planned, more than the 2 km limit for an automatic decision. A person will review it."
    return story


def build(case_id: str) -> dict:
    case = _CASE_INDEX[case_id]
    ticket = case.dispute_ticket
    evidence = [history_lookup(case), safety_check(case)]
    safety = safety_override(evidence[1].facts)
    if ticket.dispute_type == "no_show_charge":
        evidence.append(no_show_check(case))
        outcome, amount, clauses, conduct = compute_no_show_outcome(evidence[-1].facts)
    else:
        evidence.append(route_deviation(case))
        outcome, amount, clauses, conduct = compute_route_deviation_outcome(evidence[-1].facts)
    evidence.append(fare_validate(case))
    formula_outcome = outcome
    if safety:
        outcome, amount, clauses, conduct = safety
    escalated = outcome == "escalate"

    if ticket.dispute_type == "no_show_charge":
        story = _ns_story(evidence[2].facts, formula_outcome, clauses if not safety else compute_no_show_outcome(evidence[2].facts)[2])
    else:
        story = _rd_story(evidence[2].facts, formula_outcome, compute_route_deviation_outcome(evidence[2].facts)[1], compute_route_deviation_outcome(evidence[2].facts)[2])
    if safety:
        flagged = ", ".join(evidence[1].facts["keyword_hits"])
        story["exp_rider"] = story["exp_driver"] = "A safety concern was reported in this trip, so the system will not decide it automatically. A person will review it first. No money moves until they do."
        escalation_reason = f"Safety concern reported (keywords: {flagged}). Safety cases are never auto-resolved (S-1.1)."
    elif escalated:
        missing = evidence[2].facts.get("missing_evidence")
        escalation_reason = ("Missing evidence: " + ", ".join(missing)) if missing else "Deviation is over the 2 km automatic-ruling limit (RD-2.8)."
    else:
        escalation_reason = None

    briefs, log = [], []
    for side, order in (("rider", 0), ("driver", 1)):
        pos, args = story[f"{side}_pos"], story[f"{side}_args"]
        briefs.append({
            "dispute_id": ticket.dispute_id, "side": side, "position": pos,
            "arguments": [{"point": p, "evidence_refs": refs, "clauses": cl} for p, refs, cl in args],
            "weaknesses_acknowledged": [story[f"{side}_weak"]],
        })
        agent = f"{side}_advocate"
        log.append({"agent": agent, "type": "argument", "content": pos})
        for p, _, _ in args:
            log.append({"agent": agent, "type": "argument", "content": p})
        log.append({"agent": "_brief", "side": side})
    confidence = 0.5 if escalated else (0.85 if outcome == "no_action" else 0.9)
    ruling = {
        "dispute_id": ticket.dispute_id, "outcome": outcome, "amount_sgd": amount, "confidence": confidence,
        "clauses_cited": clauses, "explanation_rider": story["exp_rider"], "explanation_driver": story["exp_driver"],
        "conduct_flag": conduct, "escalated": escalated, "escalation_reason": escalation_reason,
    }
    judge = f"Ruling: {outcome}, S${amount:.2f} (confidence {confidence:.2f}). Clauses: {', '.join(clauses)}."
    if escalated:
        judge += f" Escalated: {escalation_reason}"
    log.append({"agent": "judge", "type": "ruling", "content": judge})
    return {
        "case_id": case_id, "dispute_type": ticket.dispute_type, "filed_by": ticket.filed_by,
        "evidence": [e.model_dump(mode="json") for e in evidence], "log": log, "briefs": briefs, "ruling": ruling,
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for cid in CASE_IDS:
        data = build(cid)
        (OUT / f"{cid}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        r = data["ruling"]
        print(f"{cid:9s} {data['dispute_type']:16s} -> {r['outcome']:15s} S${r['amount_sgd']:.2f} {r['clauses_cited']}")


if __name__ == "__main__":
    main()
