"""Courtroom log component — displays agent messages as they arrive."""
from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

from components.friendly import confidence_label
from components.ruling_cards import FACT_LABELS, OUTCOME_LABELS

AGENT_STYLES = {
    "rider_advocate": {"icon": "🅡", "color": "#0e8a82", "label": "Rider Advocate", "cls": "rider", "letter": "R"},
    "driver_advocate": {"icon": "🅓", "color": "#c26a12", "label": "Driver Advocate", "cls": "driver", "letter": "D"},
    "judge": {"icon": "⚖️", "color": "#5b2a86", "label": "Judge", "cls": "judge", "letter": "J"},
    "system": {"icon": "⚙️", "color": "#7a6670", "label": "System", "cls": "system", "letter": "·"},
}

LOG_HEIGHT = 450  # px; the log scrolls inside a fixed-height window

_CLAUSE_RE = re.compile(r"\b[A-Z]{1,3}-\d+(?:\.\d+)+\b")


_ADVOCATES = ("rider_advocate", "driver_advocate")
_FALLBACK_RE = re.compile(r"^(?P<claim>.*?)\s*Evidence:\s*(?P<ev>.*?)\s*(?:Clauses?:\s*(?P<cl>.*))?$", re.DOTALL)


def _prettify(text: str) -> str:
    text = text.replace("_", " ").replace(".", " ").strip()
    return text[:1].upper() + text[1:]


def humanize_ref(ref: str) -> str:
    """'no_show_check.driver_within_arrival_radius' -> 'Driver reached the pickup point'."""
    tool, _, rest = ref.partition(".")
    key = rest.split(".")[-1] if rest else ""
    if tool == "history_lookup" and key in ("rider", "driver"):
        return f"{key.capitalize()} history"
    if key and key in FACT_LABELS:
        return FACT_LABELS[key][0]
    return _prettify(ref if not key else key)


def _split_claim(raw: str) -> tuple[str, list[str], list[str]]:
    """Fallback for text that still carries 'Evidence: ... Clause: ...' (mock/demo stream)."""
    m = _FALLBACK_RE.match(raw)
    if not m:
        return raw, [], list(dict.fromkeys(_CLAUSE_RE.findall(raw)))
    refs = [r.strip() for r in re.split(r",\s*", m.group("ev")) if r.strip()]
    clauses = list(dict.fromkeys(_CLAUSE_RE.findall(m.group("cl") or "")))
    return m.group("claim").strip(), refs, clauses


def _brief_for(msg: dict[str, Any], briefs: list[dict[str, Any]] | None):
    side = str(msg.get("agent", "")).split("_")[0]
    return next((b for b in briefs or [] if b.get("side") == side), None)


def _advocate_parts(msg: dict[str, Any], briefs, technical: bool) -> tuple[str, str, list[str], str]:
    """Return (tag, claim, refs, clauses) for an advocate message, preferring the structured brief."""
    raw = str(msg.get("content", ""))
    brief = _brief_for(msg, briefs)
    if brief:
        if raw == brief.get("position"):
            return "Position", raw, [], []
        for i, arg in enumerate(brief.get("arguments", []), start=1):
            if arg.get("point") == raw:
                return f"Point {i}", raw, list(arg.get("evidence_refs", [])), list(arg.get("clauses", []))
    claim, refs, clauses = _split_claim(raw)
    tag = "Rebuttal" if msg.get("type") == "rebuttal" else ""
    return tag, claim, refs, clauses


def _chips(clauses: list[str]) -> str:
    return (
        '<div class="vp-chips">' + "".join(f'<span class="vp-chip">{html.escape(c)}</span>' for c in clauses) + "</div>"
        if clauses
        else ""
    )


def _judge_parts(msg: dict[str, Any], ruling: dict[str, Any] | None) -> tuple[str, list[str]]:
    if ruling and msg.get("type") == "ruling":
        label = OUTCOME_LABELS.get(ruling.get("outcome"), ruling.get("outcome", ""))
        if ruling.get("escalated"):
            line = f"<strong>{html.escape(label)}</strong> · {html.escape(ruling.get('escalation_reason') or '')}"
        else:
            line = (
                f"<strong>{html.escape(label)}</strong> · S${(ruling.get('amount_sgd') or 0):.2f} · "
                f"{confidence_label(ruling.get('confidence'))} confidence"
            )
        return line, list(ruling.get("clauses_cited") or [])
    raw = str(msg.get("content", ""))
    return html.escape(raw), list(dict.fromkeys(_CLAUSE_RE.findall(raw)))


def _message_html(
    msg: dict[str, Any], briefs=None, ruling=None, technical: bool = False, continued: bool = False
) -> str:
    """One chat message: advocates on opposite sides, judge centred. ``continued`` hides the
    avatar and name when the previous bubble came from the same speaker."""
    agent = msg.get("agent", "system")
    style = AGENT_STYLES.get(agent, AGENT_STYLES["system"])

    if agent not in (*_ADVOCATES, "judge"):
        content = html.escape(str(msg.get("content", "")))
        return f'<div class="vp-msg system" style="display:block;max-width:100%"><div class="vp-sys">{content}</div></div>'

    tag = ""
    based = ""
    if agent in _ADVOCATES:
        tag, claim, refs, clauses = _advocate_parts(msg, briefs, technical)
        body = html.escape(claim)
        if tag == "Position":
            body = f"<strong>{body}</strong>"
        if refs:
            shown = (
                ", ".join(f"<code>{html.escape(r)}</code>" for r in refs)
                if technical
                else " · ".join(dict.fromkeys(html.escape(humanize_ref(r)) for r in refs))
            )
            based = f'<div class="vp-based"><b>Based on</b> <em>{shown}</em></div>'
    else:
        body, clauses = _judge_parts(msg, ruling)

    tag_html = f'<span class="vp-tag">{tag}</span>' if tag else ""
    head = (
        f'<div class="vp-who">{style["label"]}{tag_html}</div>'
        if not continued
        else (f'<div class="vp-who">{tag_html}</div>' if tag else "")
    )
    cont = " cont" if continued else ""
    return (
        f'<div class="vp-msg {style["cls"]}{cont}"><div class="vp-avatar" aria-hidden="true">{style["letter"]}</div>'
        f'<div class="vp-bubble">{head}<div class="vp-claim">{body}</div>{based}{_chips(clauses)}</div></div>'
    )


def typing_html(agent: str, label: str) -> str:
    """A 'writing...' bubble shown while the next speaker prepares."""
    style = AGENT_STYLES.get(agent, AGENT_STYLES["system"])
    return (
        f'<div class="vp-msg {style["cls"]}"><div class="vp-avatar" aria-hidden="true">{style["letter"]}</div>'
        f'<div class="vp-bubble"><div class="vp-who">{html.escape(label)}</div>'
        '<span class="vp-typing" role="status" aria-label="Writing"><i></i><i></i><i></i></span></div></div>'
    )


def chat_html(
    messages: list[dict[str, Any]],
    technical: bool = False,
    trailing: str = "",
    briefs: list[dict[str, Any]] | None = None,
    ruling: dict[str, Any] | None = None,
) -> str:
    parts = []
    prev_agent = None
    for msg in messages:
        if technical and msg.get("raw"):
            msg = {**msg, "content": msg["raw"]}
        agent = msg.get("agent")
        parts.append(_message_html(msg, briefs, ruling, technical, continued=agent == prev_agent and agent != "system"))
        prev_agent = agent
    return '<div class="vp-chat">' + "".join(parts) + trailing + "</div>"


def render_courtroom_log(
    messages: list[dict[str, Any]],
    technical: bool = False,
    briefs: list[dict[str, Any]] | None = None,
    ruling: dict[str, Any] | None = None,
) -> None:
    """Render the full courtroom log as a chat in a scrollable window.

    ``technical`` shows the raw tool output lines (stored under each message's ``raw`` key)
    and the raw evidence refs.
    """
    with st.container(height=LOG_HEIGHT, border=True):
        st.markdown(chat_html(messages, technical, briefs=briefs, ruling=ruling), unsafe_allow_html=True)


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
