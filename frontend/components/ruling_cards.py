"""Ruling card and evidence card components."""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

from components.friendly import confidence_label, outcome_headline
from policy import load_clauses

OUTCOME_LABELS = {
    "refund": "Refund",
    "compensation": "Compensation",
    "no_action": "No Action",
    "charge_upheld": "Charge Upheld",
    "charge_reversed": "Charge Reversed",
    "escalate": "Escalated to Human",
}

OUTCOME_COLORS = {
    "refund": "#1a73e8",
    "compensation": "#1a73e8",
    "no_action": "#5f6368",
    "charge_upheld": "#e8451a",
    "charge_reversed": "#1a73e8",
    "escalate": "#d93025",
}

TOOL_LABELS = {
    "no_show_check": "No-Show Check",
    "route_deviation": "Route Deviation",
    "fare_validate": "Fare Validation",
    "history_lookup": "History Lookup",
    "safety_check": "Safety Check",
}

TOOL_ICONS = {
    "no_show_check": "📍",
    "route_deviation": "🗺️",
    "fare_validate": "💳",
    "history_lookup": "📋",
    "safety_check": "🛡️",
}


def verdict_banner_html(ruling: dict[str, Any]) -> str:
    """Big verdict moment: headline, one-line reason and the amount."""
    escalated = ruling.get("escalated", False)
    headline = html.escape(outcome_headline(ruling))
    if escalated:
        reason = html.escape(ruling.get("escalation_reason") or "low confidence")
        return (
            '<div class="vp-verdict review"><div>'
            f"<h3>{headline}</h3><p>Safety concerns, missing evidence and low-confidence cases are never "
            f"decided automatically. Reason: {reason}. It is now in the review queue.</p></div></div>"
        )
    amount = ruling.get("amount_sgd") or 0
    return (
        f'<div class="vp-verdict"><div><h3>{headline}</h3>'
        "<p>Each of you gets your own explanation below.</p></div>"
        f'<div class="vp-amount">${amount:.2f}</div></div>'
    )


def policy_refs_html(clauses: list[str]) -> str:
    """Clause chips; hovering (or focusing) one shows that clause's text in a small popup."""
    known = load_clauses()
    chips = []
    for i, cid in enumerate(clauses):
        info = known.get(cid)
        pop = (
            f'<span class="vp-pop" role="tooltip"><b>{html.escape(cid)} · {html.escape(info["title"])}</b>'
            f'<span>{html.escape(info["text"])}</span></span>'
            if info
            else ""
        )
        side = " right" if i >= 3 else ""
        chips.append(
            f'<span class="vp-clause{side}" tabindex="0" aria-label="Policy clause {html.escape(cid)}">'
            f"{html.escape(cid)}{pop}</span>"
        )
    return f'<div class="vp-refs"><span class="vp-refs-label">Policy references</span>{"".join(chips)}</div>'


def render_ruling_card(ruling: dict[str, Any], audience: str, highlight: bool = False) -> None:
    """Render a ruling card for either the rider or driver perspective."""
    clauses = ruling.get("clauses_cited") or []
    escalated = ruling.get("escalated", False)
    confidence = ruling.get("confidence") or 0
    explanation = (
        ruling.get("explanation_rider", "")
        if audience == "rider"
        else ruling.get("explanation_driver", "")
    )
    title = "Rider view" if audience == "rider" else "Driver view"
    you = '<span class="vp-pill">You</span>' if highlight else ""
    level = confidence_label(confidence)
    pill_cls = "good" if level == "High" else "warn" if level == "Low" else ""

    with st.container(key="view_you" if highlight else f"view_other_{audience}"):
        st.markdown(
            f'<div class="vp-viewhead"><h3>{title}</h3>{you}</div>'
            f'<div class="vp-meter" role="img" aria-label="Confidence {confidence:.0%}"><i style="width:{confidence:.0%}"></i></div>'
            f'<span class="vp-pill {pill_cls}">{level} confidence</span>'
            f'<p class="vp-why">{html.escape(explanation)}</p>',
            unsafe_allow_html=True,
        )
        if clauses:
            st.markdown(policy_refs_html(clauses), unsafe_allow_html=True)


_TILE_KEYS = {
    "no_show_check": [
        ("total_wait_min", "min", "Driver waited"),
        ("driver_distance_from_pickup_m", "m", "Driver from pickup"),
        ("contact_attempts", "", "Contact attempts"),
        ("rider_replies", "", "Rider replies"),
    ],
    "route_deviation": [
        ("deviation_pct", "%", "Extra distance"),
        ("actual_distance_km", "km", "Route taken"),
        ("baseline_distance_km", "km", "Direct route"),
        ("trip_duration_min", "min", "Trip duration"),
    ],
}


def evidence_tiles_html(evidence: list[dict[str, Any]]) -> str:
    """Key numbers from the evidence tools as small stat tiles, plus any flags."""
    tiles: list[str] = []
    for ev in evidence:
        facts = ev.get("facts", {})
        for key, unit, label in _TILE_KEYS.get(ev.get("tool", ""), []):
            value = facts.get(key)
            if value is None:
                continue
            text = f"{round(float(value), 1):g}" if isinstance(value, (int, float)) else html.escape(str(value))
            tiles.append(f'<div class="vp-tile"><b>{text}{(" " + unit) if unit else ""}</b><span>{label}</span></div>')
        for flag in ev.get("flags", []):
            tiles.append(f'<div class="vp-tile flag"><b>!</b><span>{html.escape(_humanize_flag(flag))}</span></div>')
    return '<div class="vp-tiles">' + "".join(tiles) + "</div>" if tiles else ""


def _format_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "✅ Yes" if value else "❌ No"
    if isinstance(value, float):
        return f"{round(value, 2):g}"
    if isinstance(value, list):
        return html.escape(", ".join(str(v) for v in value)) if value else "—"
    return html.escape(str(value))


FACT_LABELS = {
    "driver_distance_from_pickup_m": ("Driver distance from pickup", "m"),
    "driver_within_arrival_radius": ("Driver reached the pickup point", ""),
    "arrived_minutes_vs_scheduled": ("Arrival vs scheduled time", "min (negative = early)"),
    "total_wait_min": ("Driver waited", "min"),
    "free_wait_expired": ("Free wait period used up", ""),
    "no_show_threshold_reached": ("No-show wait reached", ""),
    "contact_attempts": ("Driver contact attempts", ""),
    "rider_replies": ("Rider replies", ""),
    "minimum_contact_attempts": ("Contact attempts required", ""),
    "missing_evidence": ("Missing evidence", ""),
    "baseline_distance_km": ("Direct route", "km"),
    "actual_distance_km": ("Route taken", "km"),
    "deviation_pct": ("Extra distance", "%"),
    "review_triggered": ("Over the deviation limit", ""),
    "rider_requested_detour": ("Rider asked for a detour", ""),
    "traffic_justified": ("Traffic explains the detour", ""),
    "trip_duration_min": ("Trip duration", "min"),
    "avg_speed_kmh": ("Average speed", "km/h"),
    "max_speed_kmh": ("Top speed", "km/h"),
    "actual_fare_sgd": ("Fare charged", "S$"),
    "per_km_rate_sgd": ("Rate per km", "S$"),
    "components_sum_sgd": ("Fare parts add up to", "S$"),
    "breakdown_consistent": ("Fare breakdown adds up", ""),
    "surge_applied": ("Surge pricing", ""),
    "fare_type": ("Fare type", ""),
    "fare_source": ("Fare source", ""),
    "safety_incident": ("Safety concern", ""),
    "speeding": ("Speeding", ""),
    "categories": ("Concerns found", ""),
    "keyword_hits": ("Concerning words", ""),
    "avg_rating": ("Average rating", ""),
    "total_trips": ("Trips", ""),
    "account_age_days": ("Account age", "days"),
    "total_disputes": ("Disputes filed", ""),
    "fraud_flags": ("Fraud flags", ""),
}

FLAG_LABELS = {
    "RD_MISSING_EVIDENCE": "Some route evidence is missing",
    "NS-1.8_MISSING_EVIDENCE": "Some pickup evidence is missing",
    "FARE_DATA_MISSING": "Some fare details are missing",
    "RIDER_FRAUD_FLAG": "Rider has a fraud flag on file",
    "DRIVER_FRAUD_FLAG": "Driver has a fraud flag on file",
}


def _humanize_flag(flag: str) -> str:
    if flag in FLAG_LABELS:
        return FLAG_LABELS[flag]
    return flag.replace("_", " ").capitalize() if flag.isupper() else flag


def _facts_html(facts: dict[str, Any], depth: int = 0, technical: bool = False) -> str:
    """A (possibly nested) facts dict as compact, indented label/value lines in one HTML block."""
    rows: list[str] = []
    for key, value in facts.items():
        if not technical and (value is None or value == [] or value == {}):
            continue
        label, unit = FACT_LABELS.get(key, (key.replace("_", " ").capitalize(), ""))
        if technical:
            label = key
        pad = f' style="margin-left:{depth * 16}px"' if depth else ""
        if isinstance(value, dict):
            rows.append(f'<div class="vp-fact head"{pad}><b>{html.escape(label)}</b></div>')
            rows.append(_facts_html(value, depth + 1, technical))
        else:
            suffix = f" {unit}" if unit and not isinstance(value, bool) and value is not None else ""
            rows.append(
                f'<div class="vp-fact"{pad}><b>{html.escape(label)}</b><span class="sep">: </span>'
                f'<span class="v">{_format_value(value)}{suffix}</span></div>'
            )
    return "".join(rows)


def _render_facts(facts: dict[str, Any], depth: int = 0, technical: bool = False, roomy: bool = False) -> None:
    cls = "vp-facts roomy" if roomy else "vp-facts"
    st.markdown(f'<div class="{cls}">{_facts_html(facts, depth, technical)}</div>', unsafe_allow_html=True)


DIALOG_BODY_HEIGHT = 480  # px; the expanded view scrolls inside this window


def _render_evidence_body(evidence: dict[str, Any], technical: bool) -> None:
    """Full facts and flags for the expanded view, in a scrollable window with roomy rows."""
    tool = evidence.get("tool", "unknown")
    with st.container(height=DIALOG_BODY_HEIGHT, border=False):
        if technical:
            st.caption(f"Dispute {evidence.get('dispute_id', '—')} · tool: {tool}")
        for flag in evidence.get("flags", []):
            st.warning(f"⚠️ {_humanize_flag(flag)}")
        _render_facts(evidence.get("facts", {}), technical=technical, roomy=True)


def _open_evidence_dialog(evidence: dict[str, Any], technical: bool) -> None:
    tool = evidence.get("tool", "unknown")
    title = f"{TOOL_ICONS.get(tool, '🔧')} {TOOL_LABELS.get(tool, tool)}"

    def body() -> None:
        _render_evidence_body(evidence, technical)

    st.dialog(title, width="large")(body)()


def _card_html(evidence: dict[str, Any], technical: bool) -> str:
    """Fixed-height card: clickable title and flags, a scrollable facts area, a clickable footer."""
    tool = evidence.get("tool", "unknown")
    flags = "".join(
        f'<span class="vp-pill warn">{html.escape(_humanize_flag(f))}</span>' for f in evidence.get("flags", [])
    )
    flags_html = f'<div class="vp-evflags">{flags}</div>' if flags else ""
    return (
        '<div class="vp-evcard">'
        f'<div class="vp-evhead">{TOOL_ICONS.get(tool, "🔧")} {html.escape(TOOL_LABELS.get(tool, tool))}</div>'
        f'{flags_html}<div class="vp-evbody"><div class="vp-facts">'
        f'{_facts_html(evidence.get("facts", {}), technical=technical)}</div></div>'
        '<div class="vp-evhint">Open full view ›</div></div>'
    )


def render_evidence_card(evidence: dict[str, Any], technical: bool = False, index: int = 0) -> None:
    """Render an evidence tool output card.

    Expected schema (see schemas.md §2 Evidence output):
        dispute_id, tool, facts (dict), flags (list[str])

    Every card has the same height. The title, flags and footer are a click target (an invisible
    button laid under the facts area) that opens the full facts in a dialog; the facts area
    scrolls on its own.
    """
    tool = evidence.get("tool", "unknown")
    label = TOOL_LABELS.get(tool, tool)
    with st.container(key=f"evcard_{index}_{tool}"):
        if st.button(f"Open {label} details", key=f"evbtn_{index}_{tool}"):
            _open_evidence_dialog(evidence, technical)
        st.markdown(_card_html(evidence, technical), unsafe_allow_html=True)
