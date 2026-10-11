"""Ruling card and evidence card components."""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

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


def render_ruling_card(ruling: dict[str, Any], audience: str) -> None:
    """Render a ruling card for either the rider or driver perspective."""
    outcome = ruling.get("outcome", "no_action")
    label = OUTCOME_LABELS.get(outcome, outcome)
    color = OUTCOME_COLORS.get(outcome, "#5f6368")
    confidence = ruling.get("confidence") or 0
    amount = ruling.get("amount_sgd") or 0
    clauses = ruling.get("clauses_cited") or []
    escalated = ruling.get("escalated", False)

    explanation = (
        ruling.get("explanation_rider", "")
        if audience == "rider"
        else ruling.get("explanation_driver", "")
    )

    title = "Rider View" if audience == "rider" else "Driver View"

    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(
            f"<span style='color:{color};font-weight:700;font-size:1.2em;'>{label}</span>",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        if outcome != "escalate":
            col1.metric("Amount (SGD)", f"${amount:.2f}")
        col2.metric("Confidence", f"{confidence:.0%}")

        st.markdown("**Clauses cited**")
        st.markdown(" ".join(f"`{c}`" for c in clauses) if clauses else "—")

        st.markdown("**Explanation**")
        st.info(explanation)

        if escalated:
            st.warning(
                f"⚠️ Escalated to human review: {ruling.get('escalation_reason', 'low confidence')}"
            )


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


def _humanize_flag(flag: str) -> str:
    return flag.replace("_", " ").capitalize() if flag.isupper() else flag


def _render_facts(facts: dict[str, Any], depth: int = 0) -> None:
    """Render a (possibly nested) facts dict as indented key/value lines."""
    indent = "&nbsp;" * 4 * depth
    for key, value in facts.items():
        display_key = key.replace("_", " ").title()
        if isinstance(value, dict):
            st.markdown(f"{indent}**{display_key}**", unsafe_allow_html=True)
            _render_facts(value, depth + 1)
        else:
            st.markdown(f"{indent}**{display_key}**: {_format_value(value)}", unsafe_allow_html=True)


def render_evidence_card(evidence: dict[str, Any]) -> None:
    """Render an evidence tool output card.

    Expected schema (see schemas.md §2 Evidence output):
        dispute_id, tool, facts (dict), flags (list[str])
    """
    tool = evidence.get("tool", "unknown")
    facts = evidence.get("facts", {})
    flags = evidence.get("flags", [])
    label = TOOL_LABELS.get(tool, tool)
    icon = TOOL_ICONS.get(tool, "🔧")

    with st.container(border=True):
        st.markdown(f"#### {icon} {label}")
        st.caption(f"Dispute {evidence.get('dispute_id', '—')}")

        _render_facts(facts)

        if flags:
            for flag in flags:
                st.warning(f"⚠️ {_humanize_flag(flag)}")
