"""Courtroom log component — displays agent messages as they arrive."""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

AGENT_STYLES = {
    "rider_advocate": {"icon": "🅡", "color": "#1a73e8", "label": "Rider Advocate"},
    "driver_advocate": {"icon": "🅓", "color": "#e8451a", "label": "Driver Advocate"},
    "judge": {"icon": "⚖️", "color": "#6b21a8", "label": "Judge"},
    "system": {"icon": "⚙️", "color": "#5f6368", "label": "System"},
}

LOG_HEIGHT = 450  # px; the log scrolls inside a fixed-height window

TYPE_ICONS = {
    "evidence": "🔍",
    "argument": "📋",
    "rebuttal": "⚡",
    "ruling": "⚖️",
}


def _message_html(msg: dict[str, Any]) -> str:
    """Build the HTML for a single agent message bubble."""
    agent = msg.get("agent", "system")
    msg_type = msg.get("type", "evidence")
    content = html.escape(str(msg.get("content", "")))
    style = AGENT_STYLES.get(agent, AGENT_STYLES["system"])
    type_icon = TYPE_ICONS.get(msg_type, "•")

    return f"""
        <div style="
            border-left: 3px solid {style['color']};
            padding: 8px 12px;
            margin: 6px 0;
            background: #f8f9fa;
            border-radius: 0 4px 4px 0;
        ">
            <span style="color:{style['color']};font-weight:600;">
                {type_icon} {style['label']}
            </span>
            <span style="color:#80868b;font-size:0.8em;margin-left:8px;">
                {msg_type}
            </span>
            <div style="margin-top:4px;color:#202124;">{content}</div>
        </div>
    """


def render_message(msg: dict[str, Any]) -> None:
    """Render a single agent message as a styled bubble."""
    st.markdown(_message_html(msg), unsafe_allow_html=True)


def render_courtroom_log(messages: list[dict[str, Any]], technical: bool = False) -> None:
    """Render the full courtroom log in a scrollable window.

    ``technical`` shows the raw tool output lines stored under each message's ``raw`` key.
    """
    with st.container(height=LOG_HEIGHT, border=True):
        for msg in messages:
            if technical and msg.get("raw"):
                msg = {**msg, "content": msg["raw"]}
            render_message(msg)


def render_briefs(briefs: list[dict[str, Any]], expanded: bool = False) -> None:
    """Show each advocate's structured brief: position, cited arguments, weaknesses."""
    cols = st.columns(len(briefs)) if briefs else []
    for col, brief in zip(cols, sorted(briefs, key=lambda b: b.get("side", ""), reverse=True)):
        style = AGENT_STYLES.get(f"{brief.get('side')}_advocate", AGENT_STYLES["system"])
        with col:
            st.markdown(f"**{style['icon']} {style['label']}**")
            st.markdown(f"_{brief.get('position', '')}_")
            for arg in brief.get("arguments", []):
                st.markdown(f"- {arg.get('point', '')}")
                refs = ", ".join(f"`{r}`" for r in arg.get("evidence_refs", []))
                clauses = ", ".join(f"`{c}`" for c in arg.get("clauses", []))
                st.caption(f"Evidence: {refs} · Policy: {clauses}")
            weaknesses = brief.get("weaknesses_acknowledged") or []
            if weaknesses:
                st.markdown("**Weaknesses acknowledged**")
                for w in weaknesses:
                    st.markdown(f"- {w}")
