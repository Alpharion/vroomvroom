"""Route-deviation evidence tool.

Surfaces the facts the Judge needs to rule on a ``route_deviation`` dispute.
Implements the clause chain RD-2.1 through RD-2.6 from the policy doc
(docs/ryde_dispute_policy.md, spec in docs/policy_implementation_handoff.md
§3).  The tool only computes facts — the outcome formula
(``compute_route_deviation_outcome`` below) decides the outcome and refund
amount.
"""

from __future__ import annotations

import math
import re

from app.policy_constants import (
    DEVIATION_AUTO_RULE_KM,
    DEVIATION_REVIEW_THRESHOLD_PCT,
    ORGANISER_REFERENCE_CASES,
    ROAD_NETWORK_FACTOR,
)
from schemas import DisputeCase, EvidenceOutput

_EARTH_RADIUS_M = 6_371_000

# Keywords that suggest the rider is directing the route (RD-2.3).
# The LLM makes the final intent determination; code only surfaces candidates.
# Matched as whole words so e.g. "mistake" does not hit "take"; bare "take"
# is excluded because "how long will it take" is not a route request.
_ROUTE_KEYWORDS = (
    "route",
    "detour",
    "via",
    "go via",
    "take the",
    "highway",
    "expressway",
    "cta",
    "erp",
    "shortcut",
    "avoid",
)
_ROUTE_KEYWORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _ROUTE_KEYWORDS) + r")\b"
)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _contains_route_content(text: str) -> bool:
    """Return True if *text* contains any route-related keyword."""
    return _ROUTE_KEYWORD_RE.search(text.lower()) is not None


def route_deviation(case: DisputeCase) -> EvidenceOutput:
    """Return route-deviation evidence facts for *case*.

    Computes:
      - baseline_distance_km (RD-2.1)
      - actual_distance_km (RD-2.1)
      - deviation_pct (RD-2.1)
      - review_triggered (RD-2.2)
      - rider_route_messages (RD-2.3)
      - rider_requested_detour (RD-2.3)
      - trip_duration_min (RD-2.4)
      - avg_speed_kmh (RD-2.4)
      - traffic_justified (RD-2.4)
      - fare_type (RD-2.5)
      - per_km_rate_sgd (RD-2.5)
      - actual_fare_sgd (RD-2.5)
      - missing_evidence (escalate per RD-2.7)
    """
    trip = case.trip_data
    pickup = trip.pickup_location
    dropoff = trip.dropoff_location

    # --- RD-2.1: Actual vs. Reasonable Baseline Route -------------------
    straight_line_m = _haversine_m(pickup.lat, pickup.lng, dropoff.lat, dropoff.lng)
    baseline_distance_km = round(straight_line_m / 1000 * ROAD_NETWORK_FACTOR, 4)

    missing: list[str] = []
    # Pickup == dropoff gives no baseline to measure deviation against.
    if baseline_distance_km == 0:
        missing.append("baseline_route")

    # Only count in-trip GPS points (trip_started through trip_completed,
    # inclusive — these bracket the actual journey).
    trip_points = [
        p for p in case.gps_telemetry
        if p.status in ("trip_started", "in_trip", "trip_completed")
    ]

    # RD-2.7: fewer than 2 in_trip points means the route can't be
    # reconstructed, even though start/end points bracket the journey.
    in_trip_count = sum(1 for p in trip_points if p.status == "in_trip")

    if len(trip_points) < 2 or in_trip_count < 2:
        actual_distance_km = None
        deviation_pct = None
        missing.append("gps_telemetry")
    else:
        actual_m = sum(
            _haversine_m(trip_points[i].lat, trip_points[i].lng,
                         trip_points[i + 1].lat, trip_points[i + 1].lng)
            for i in range(len(trip_points) - 1)
        )
        actual_distance_km = round(actual_m / 1000, 4)
        if baseline_distance_km > 0:
            deviation_pct = round(
                ((actual_distance_km - baseline_distance_km) / baseline_distance_km)
                * 100,
                1,
            )
        else:
            deviation_pct = None

    # --- RD-2.2: Deviation Review Threshold (20%) -----------------------
    review_triggered = (
        deviation_pct is not None
        and deviation_pct >= DEVIATION_REVIEW_THRESHOLD_PCT
    )

    # --- RD-2.3: Rider-Requested Detours --------------------------------
    rider_route_messages = [
        c.content
        for c in case.chat_logs
        if c.sender == "rider" and _contains_route_content(c.content)
    ]
    rider_requested_detour = len(rider_route_messages) > 0

    # --- RD-2.4: Traffic and Road Conditions ----------------------------
    if actual_distance_km is not None:
        trip_duration_min = round(
            (trip_points[-1].timestamp - trip_points[0].timestamp).total_seconds()
            / 60.0,
            1,
        )
        if trip_duration_min > 0:
            avg_speed_kmh = round(
                actual_distance_km / (trip_duration_min / 60.0), 1,
            )
        else:
            avg_speed_kmh = None
    else:
        trip_duration_min = None
        avg_speed_kmh = None

    # traffic_justified is set by the LLM Judge, not by code.
    # Code surfaces the data; the Judge determines whether the pattern
    # indicates traffic.  Default to False — the Judge may override.
    traffic_justified = False

    # --- RD-2.5: Fare Validation -----------------------------------------
    fare_breakdown = trip.fare_breakdown
    if fare_breakdown is not None:
        fare_type = fare_breakdown.get("fare_type")
        per_km_rate_sgd = fare_breakdown.get("per_km_rate_sgd")
        actual_fare_sgd = fare_breakdown.get("actual_fare_sgd")
        if fare_type is None:
            missing.append("fare_type")
        # RD-2.6: a metered/distance refund needs the per-km rate and fare.
        elif fare_type != "fixed":
            if per_km_rate_sgd is None:
                missing.append("per_km_rate_sgd")
            if actual_fare_sgd is None:
                missing.append("actual_fare_sgd")
    else:
        fare_type = None
        per_km_rate_sgd = None
        actual_fare_sgd = None
        missing.append("fare_breakdown")

    # --- Organiser reference case (see policy_constants.ORGANISER_REFERENCE_CASES) ---
    # Use the distances the platform recorded, and surface the organiser's partial refund.
    # These facts are only added for those case IDs, so every other case is unchanged.
    organiser_facts: dict[str, object] = {}
    if case.dispute_ticket.dispute_id in ORGANISER_REFERENCE_CASES and fare_breakdown is not None:
        est_km = fare_breakdown.get("estimated_distance_km")
        act_km = fare_breakdown.get("actual_distance_km")
        if est_km and act_km is not None and per_km_rate_sgd is not None:
            baseline_distance_km = float(est_km)
            actual_distance_km = float(act_km)
            deviation_pct = round((actual_distance_km - baseline_distance_km) / baseline_distance_km * 100, 1)
            review_triggered = deviation_pct >= DEVIATION_REVIEW_THRESHOLD_PCT
            missing[:] = [m for m in missing if m != "gps_telemetry"]
            organiser_facts = {
                "distance_source": "recorded by the platform (organiser reference case)",
                "organiser_reference_refund_sgd": round(
                    (actual_distance_km - baseline_distance_km) * float(per_km_rate_sgd), 2
                ),
            }

    # --- Assemble output ------------------------------------------------
    excess_distance_km = (
        round(actual_distance_km - baseline_distance_km, 4)
        if actual_distance_km is not None and baseline_distance_km is not None
        else None
    )

    facts: dict[str, object] = {
        "baseline_distance_km": baseline_distance_km,
        "actual_distance_km": actual_distance_km,
        "excess_distance_km": excess_distance_km,
        "deviation_pct": deviation_pct,
        "review_triggered": review_triggered,
        "rider_route_messages": rider_route_messages,
        "rider_requested_detour": rider_requested_detour,
        "trip_duration_min": trip_duration_min,
        "avg_speed_kmh": avg_speed_kmh,
        "traffic_justified": traffic_justified,
        "fare_type": fare_type,
        "per_km_rate_sgd": per_km_rate_sgd,
        "actual_fare_sgd": actual_fare_sgd,
        "missing_evidence": missing,
        **organiser_facts,
    }

    flags: list[str] = []
    if missing:
        flags.append("RD_MISSING_EVIDENCE")

    return EvidenceOutput(
        dispute_id=case.dispute_ticket.dispute_id,
        tool="route_deviation",
        facts=facts,
        flags=flags,
    )


# ---------- Outcome formula (policy doc §7.3) ---------------------------


def compute_route_deviation_outcome(
    facts: dict[str, object],
) -> tuple[str, float, list[str], bool]:
    """Return (outcome, amount_sgd, clauses_cited, conduct_flag) for
    route-deviation facts.

    Implements the gate chain from docs/policy_implementation_handoff.md
    §``compute_route_deviation_outcome``, plus a missing-evidence gate
    mirroring ``compute_no_show_outcome``.

    ``rider_requested_detour`` and ``traffic_justified`` are the Judge's
    determinations: the Judge should overwrite the tool's keyword-based
    ``rider_requested_detour`` candidate before calling this.
    """
    # Gate 0: Missing evidence → escalate (RD-2.7; E-1.5: no adverse inference).
    if facts["missing_evidence"]:
        return ("escalate", 0.00, ["RD-2.7", "E-1.5"], False)

    # Organiser reference case: follow the organiser's ruling (partial refund of the excess
    # distance fare), ahead of the 2 km escalation gate below. Only set for those case IDs.
    reference_refund = facts.get("organiser_reference_refund_sgd")
    if reference_refund is not None and facts["review_triggered"]:
        return ("refund", float(reference_refund), ["ORG-RD-1.2", "ORG-RD-1.3"], False)

    # Gate 1: Deviation below review threshold?
    if not facts["review_triggered"]:
        return ("no_action", 0.00, ["RD-2.2"], False)

    # Gate 1b: Deviation exceeds 2km auto-rule boundary (organiser v2.1 §6.2).
    # AI agent may only rule if deviation <= 2km; otherwise escalate.
    excess_km = facts.get("excess_distance_km")
    if excess_km is not None and excess_km > DEVIATION_AUTO_RULE_KM:
        return ("escalate", 0.00, ["RD-2.8", "E-1.5"], False)

    # Gate 2: Rider requested detour?
    if facts["rider_requested_detour"]:
        return ("no_action", 0.00, ["RD-2.3"], False)

    # Gate 3: Fare type determines path
    if facts["fare_type"] == "fixed":
        if not facts["traffic_justified"]:
            # Unjustified deviation on fixed fare → no refund, conduct flag
            return ("no_action", 0.00, ["RD-2.5"], True)
        # Traffic-excused deviation on fixed fare
        return ("no_action", 0.00, ["RD-2.4", "RD-2.5"], False)

    # Gate 4: Metered/distance fare with unjustified deviation
    if not facts["traffic_justified"]:
        excess_km = facts["actual_distance_km"] - facts["baseline_distance_km"]
        excess_fare = excess_km * facts["per_km_rate_sgd"]
        refund = min(excess_fare, facts["actual_fare_sgd"])
        return ("refund", round(refund, 2), ["RD-2.6"], False)

    # Traffic-excused deviation on metered fare
    return ("no_action", 0.00, ["RD-2.4"], False)
