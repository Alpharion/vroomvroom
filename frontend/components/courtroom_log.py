"""Courtroom log component — displays agent messages as they arrive."""
from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

AGENT_STYLES = {
    "rider_advocate": {"icon": "🅡", "color": "#0e8a82", "label": "Rider Advocate", "cls": "rider", "letter": "R"},
    "driver_advocate": {"icon": "🅓", "color": "#c26a12", "label": "Driver Advocate", "cls": "driver", "letter": "D"},
    "judge": {"icon": "⚖️", "color": "#5b2a86", "label": "Judge", "cls": "judge", "letter": "J"},
    "system": {"icon": "⚙️", "color": "#7a6670", "label": "System", "cls": "system", "letter": "·"},
}

LOG_HEIGHT = 450  # px; the log scrolls inside a fixed-height window

_CLAUSE_RE = re.compile(r"\b[A-Z]{1,3}-\d+(?:\.\d+)+\b")


def _message_html(msg: dict[str, Any]) -> str:
    """Build the HTML for a single chat message: advocates on opposite sides, judge centred."""
    agent = msg.get("agent", "system")
    raw = str(msg.get("content", ""))
    content = html.escape(raw)
    style = AGENT_STYLES.get(agent, AGENT_STYLES["system"])

    if agent not in ("rider_advocate", "driver_advocate", "judge"):
        return f'<div class="vp-msg system" style="display:block;max-width:100%"><div class="vp-sys">{content}</div></div>'

    clauses = list(dict.fromkeys(_CLAUSE_RE.findall(raw)))
    chips = (
        '<div class="vp-chips">' + "".join(f'<span class="vp-chip">{html.escape(c)}</span>' for c in clauses) + "</div>"
        if clauses
        else ""
    )
    return (
        f'<div class="vp-msg {style["cls"]}"><div class="vp-avatar" aria-hidden="true">{style["letter"]}</div>'
        f'<div class="vp-bubble"><div class="vp-who">{style["label"]}</div>{content}{chips}</div></div>'
    )


def typing_html(agent: str, label: str) -> str:
    """A 'writing...' bubble shown while the next speaker prepares."""
    style = AGENT_STYLES.get(agent, AGENT_STYLES["system"])
    return (
        f'<div class="vp-msg {style["cls"]}"><div class="vp-avatar" aria-hidden="true">{style["letter"]}</div>'
        f'<div class="vp-bubble"><div class="vp-who">{html.escape(label)}</div>'
        '<span class="vp-typing" role="status" aria-label="Writing"><i></i><i></i><i></i></span></div></div>'
    )


def chat_html(messages: list[dict[str, Any]], technical: bool = False, trailing: str = "") -> str:
    parts = []
    for msg in messages:
        if technical and msg.get("raw"):
            msg = {**msg, "content": msg["raw"]}
        parts.append(_message_html(msg))
    return '<div class="vp-chat">' + "".join(parts) + trailing + "</div>"


def render_courtroom_log(messages: list[dict[str, Any]], technical: bool = False) -> None:
    """Render the full courtroom log as a chat in a scrollable window.

    ``technical`` shows the raw tool output lines stored under each message's ``raw`` key.
    """
    with st.container(height=LOG_HEIGHT, border=True):
        st.markdown(chat_html(messages, technical), unsafe_allow_html=True)


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
