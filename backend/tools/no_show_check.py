"""No-show evidence tool.

Surfaces the facts the Judge needs to rule on a ``no_show_charge`` dispute.
Implements the gate chain NS-1.1 through NS-1.8 from the policy doc
(docs/ryde_dispute_policy.md). The tool only computes facts — the outcome
formula (policy doc §7.3, ``compute_no_show_outcome``) decides the outcome
and is part of the "refund in code" work scheduled for Sat 10 Oct.
"""

from __future__ import annotations

import math
from datetime import datetime

from app.policy_constants import (
    ARRIVAL_RADIUS_M,
    CANCELLATION_FEE_SGD,
    FREE_WAIT_TIME_MIN,
    MINIMUM_CONTACT_ATTEMPTS,
    NO_SHOW_THRESHOLD_MIN,
)
from schemas import DisputeCase, EvidenceOutput

_EARTH_RADIUS_M = 6_371_000


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


def _is_between(t: datetime, start: datetime, end: datetime) -> bool:
    """Return True if *t* is in the half-open interval [start, end]."""
    return start <= t <= end


def no_show_check(case: DisputeCase) -> EvidenceOutput:
    """Return no-show evidence facts for *case*.

    Computes:
      - driver_distance_from_pickup_m (NS-1.1)
      - driver_within_arrival_radius (NS-1.1)
      - arrived_minutes_vs_scheduled (NS-1.2)
      - total_wait_min (NS-1.3 / NS-1.4)
      - free_wait_expired (NS-1.3)
      - no_show_threshold_reached (NS-1.4)
      - contact_attempts (NS-1.5)
      - driver_messages (NS-1.5)
      - driver_calls (NS-1.5)
      - contact_requirement_met (NS-1.5)
      - rider_replies (NS-1.5)
      - missing_evidence (NS-1.8)
    """
    trip = case.trip_data
    pickup = trip.pickup_location

    # Use policy from the case if present, otherwise fall back to constants.
    if case.cancellation_policy is not None:
        free_wait_min = case.cancellation_policy.free_wait_time_min
        no_show_threshold_min = case.cancellation_policy.no_show_threshold_min
    else:
        free_wait_min = FREE_WAIT_TIME_MIN
        no_show_threshold_min = NO_SHOW_THRESHOLD_MIN

    # --- NS-1.1: Driver GPS arrival verification ---------------------------
    # Only accept points explicitly marked arrived/waiting. Do not fall back to
    # the first speed=0 point, which could be a red light en-route.
    arrived_gps = next(
        (p for p in case.gps_telemetry if p.status in ("arrived", "waiting")),
        None,
    )

    if arrived_gps is not None:
        driver_distance_from_pickup_m = round(
            _haversine_m(pickup.lat, pickup.lng, arrived_gps.lat, arrived_gps.lng),
            1,
        )
        driver_within_arrival_radius = driver_distance_from_pickup_m <= ARRIVAL_RADIUS_M
    else:
        driver_distance_from_pickup_m = None
        driver_within_arrival_radius = False

    # --- NS-1.2: Scheduled pickup time verification -----------------------
    arrival_time = trip.driver_arrival_time
    if arrival_time is None and arrived_gps is not None:
        arrival_time = arrived_gps.timestamp

    if arrival_time is not None and trip.scheduled_time is not None:
        arrived_minutes_vs_scheduled = round(
            (arrival_time - trip.scheduled_time).total_seconds() / 60.0, 1,
        )
    else:
        arrived_minutes_vs_scheduled = None

    # --- NS-1.3 / NS-1.4: Waiting period -----------------------------------
    wait_start = trip.driver_wait_start
    if wait_start is None and arrived_gps is not None:
        wait_start = arrived_gps.timestamp

    if wait_start is not None and trip.cancellation_time is not None:
        total_wait_min = round(
            (trip.cancellation_time - wait_start).total_seconds() / 60.0, 1,
        )
    else:
        total_wait_min = None

    free_wait_expired = (
        total_wait_min is not None and total_wait_min >= free_wait_min
    )
    no_show_threshold_reached = (
        total_wait_min is not None and total_wait_min >= no_show_threshold_min
    )

    # --- NS-1.5: Contact attempts (organiser v2.1 §2.3) -----------------
    # Organiser policy requires at least 1 in-app chat message AND 1 phone call.
    # We count each type separately and check both are present.
    wait_end = trip.cancellation_time

    def _in_wait_period(t: datetime) -> bool:
        if wait_start is None or wait_end is None:
            return False
        return _is_between(t, wait_start, wait_end)

    driver_messages = sum(
        1
        for c in case.chat_logs
        if c.sender == "driver"
        and c.type == "message"
        and _in_wait_period(c.timestamp)
    )
    driver_calls = sum(
        1
        for c in case.chat_logs
        if c.sender == "driver"
        and c.type == "call"
        and _in_wait_period(c.timestamp)
    )
    # Also count app_events: driver_called_rider, but only when there is no
    # matching chat_logs call entry at the same timestamp (avoid double-count).
    call_timestamps = {
        c.timestamp
        for c in case.chat_logs
        if c.sender == "driver" and c.type == "call" and _in_wait_period(c.timestamp)
    }
    app_calls = sum(
        1
        for e in case.app_events
        if e.event_type == "driver_called_rider"
        and e.timestamp not in call_timestamps
        and _in_wait_period(e.timestamp)
    )
    driver_calls += app_calls

    contact_attempts = driver_messages + driver_calls
    # Organiser v2.1 §2.3: must have at least 1 message AND 1 call.
    contact_requirement_met = driver_messages >= 1 and driver_calls >= 1

    rider_replies = sum(
        1
        for c in case.chat_logs
        if c.sender == "rider" and _in_wait_period(c.timestamp)
    )

    # --- NS-1.8: Missing evidence handling --------------------------------
    missing: list[str] = []

    if not case.gps_telemetry:
        missing.append("gps_telemetry")
    elif not any(p.status in ("arrived", "waiting") for p in case.gps_telemetry):
        missing.append("gps_telemetry (no arrived/waiting points)")

    if trip.driver_arrival_time is None and arrived_gps is None:
        missing.append("driver_arrival_time")

    if trip.cancellation_time is None:
        missing.append("cancellation_time")

    if not case.chat_logs:
        missing.append("chat_logs")

    # --- Assemble output ---------------------------------------------------
    facts: dict[str, object] = {
        "driver_distance_from_pickup_m": driver_distance_from_pickup_m,
        "driver_within_arrival_radius": driver_within_arrival_radius,
        "arrived_minutes_vs_scheduled": arrived_minutes_vs_scheduled,
        "total_wait_min": total_wait_min,
        "free_wait_expired": free_wait_expired,
        "no_show_threshold_reached": no_show_threshold_reached,
        "contact_attempts": contact_attempts,
        "driver_messages": driver_messages,
        "driver_calls": driver_calls,
        "contact_requirement_met": contact_requirement_met,
        "rider_replies": rider_replies,
        "minimum_contact_attempts": MINIMUM_CONTACT_ATTEMPTS,
        "missing_evidence": missing,
    }

    flags: list[str] = []
    if missing:
        flags.append("NS-1.8_MISSING_EVIDENCE")
    if arrived_minutes_vs_scheduled is not None and arrived_minutes_vs_scheduled > 0:
        flags.append("NS-1.2_LATE_ARRIVAL")

    return EvidenceOutput(
        dispute_id=case.dispute_ticket.dispute_id,
        tool="no_show_check",
        facts=facts,
        flags=flags,
    )


# ---------- Outcome formula (policy doc §7) -----------------------------


def compute_no_show_outcome(
    facts: dict[str, object],
) -> tuple[str, float, list[str], bool]:
    """Return (outcome, amount_sgd, clauses_cited, conduct_flag) for
    no-show facts.

    Implements the gate chain from docs/policy_implementation_handoff.md
    §``compute_no_show_outcome``.  ``conduct_flag`` is always False for
    no-show disputes.
    """
    # Gate 0: Missing evidence → escalate (E-1.5: no adverse inference).
    if facts["missing_evidence"]:
        return ("escalate", 0.00, ["NS-1.8", "E-1.5"], False)

    # Gate 1: Driver arrived?
    if not facts["driver_within_arrival_radius"]:
        return ("charge_reversed", CANCELLATION_FEE_SGD, ["NS-1.1", "NS-1.7"], False)

    # Gate 2: Free wait expired?
    if not facts["free_wait_expired"]:
        return ("charge_reversed", CANCELLATION_FEE_SGD, ["NS-1.3", "NS-1.7"], False)

    # Gate 3: No-show threshold reached?
    if not facts["no_show_threshold_reached"]:
        return ("charge_reversed", CANCELLATION_FEE_SGD, ["NS-1.4", "NS-1.7"], False)

    # Gate 4: Contact requirement (organiser v2.1 §2.3: 1 message AND 1 call)?
    if not facts["contact_requirement_met"]:
        return ("charge_reversed", CANCELLATION_FEE_SGD, ["NS-1.5", "NS-1.7"], False)

    # All gates passed
    return ("charge_upheld", CANCELLATION_FEE_SGD, ["NS-1.6"], False)
