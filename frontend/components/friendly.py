"""Plain-language wording for evidence, rulings and errors."""
from __future__ import annotations

from typing import Any


def _n(value: Any, digits: int = 1) -> str:
    return f"{round(float(value), digits):g}"


def friendly_evidence_line(tool: str, facts: dict[str, Any], flags: list[str] | None = None) -> str | None:
    """One readable sentence for an evidence tool's output, or None to fall back to the raw text."""
    try:
        if tool == "no_show_check":
            if facts.get("missing_evidence"):
                return "Checked the pickup, but some evidence is missing: " + ", ".join(
                    str(m).replace("_", " ") for m in facts["missing_evidence"]
                ) + "."
            diff = facts.get("arrived_minutes_vs_scheduled")
            when = ""
            if diff is not None:
                when = f"{_n(abs(diff))} min {'early' if diff <= 0 else 'late'}, "
            return (
                f"Checked the pickup: the driver arrived {when}"
                f"{_n(facts['driver_distance_from_pickup_m'], 0)} m from the pickup point, "
                f"waited {_n(facts['total_wait_min'])} min, made {facts['contact_attempts']} contact "
                f"attempt(s) and got {facts['rider_replies']} reply(ies)."
            )
        if tool == "route_deviation":
            if facts.get("missing_evidence"):
                return "Compared the routes, but the GPS record is incomplete."
            extra = f" ({_n(facts['deviation_pct'])}% longer)" if facts.get("deviation_pct") is not None else ""
            return (
                f"Compared the routes: the driver went {_n(facts['actual_distance_km'], 2)} km "
                f"against a direct {_n(facts['baseline_distance_km'], 2)} km{extra}."
            )
        if tool == "history_lookup":
            r, d = facts["rider"], facts["driver"]
            return (
                f"Checked history: the rider has {r['total_trips']} trips rated {_n(r['avg_rating'])}; "
                f"the driver has {d['total_trips']} trips rated {_n(d['avg_rating'])}."
            )
        if tool == "safety_check":
            if facts.get("safety_incident"):
                return ("Safety check: possible safety concern found ("
                        + ", ".join(facts.get("categories") or ["see details"])
                        + "). A person will review this case.")
            return "Safety check: no safety concerns found."
        if tool == "fare_validate":
            line = f"Checked the fare: S${_n(facts['actual_fare_sgd'], 2)}"
            if facts.get("breakdown_consistent") is True:
                line += ", and the breakdown adds up."
            elif facts.get("breakdown_consistent") is False:
                line += ", but the breakdown does not add up."
            else:
                line += "."
            return line
    except (KeyError, TypeError, ValueError):
        return None
    return None


def outcome_headline(ruling: dict[str, Any]) -> str:
    amount = ruling.get("amount_sgd") or 0
    return {
        "charge_upheld": f"The S${amount:.2f} no-show fee stands.",
        "charge_reversed": "The no-show fee has been reversed.",
        "refund": f"A refund of S${amount:.2f} is due to the rider.",
        "compensation": f"Compensation of S${amount:.2f} has been awarded.",
        "no_action": "No refund or fee change.",
        "escalate": "A person will review this case.",
    }.get(ruling.get("outcome"), "Decision recorded.")


def confidence_label(confidence: float | None) -> str:
    c = confidence or 0
    return "High" if c >= 0.85 else "Medium" if c >= 0.7 else "Low"


def friendly_error(message: str) -> str:
    if "Unknown dispute ID" in message:
        return "We couldn't find that case. Please pick a trip from the list."
    if "too long" in message:
        return "This is taking longer than expected. Please try again."
    return "We couldn't finish reviewing your dispute. Please try again in a moment."
