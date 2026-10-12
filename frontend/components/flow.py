"""Progress stepper shown above the dispute flow."""
from __future__ import annotations

import streamlit as st

STAGES = ["Filed", "Evidence", "Advocates", "Judge", "Ruling"]

STEPPER_CSS = """
<style>
.rt-stepper{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 14px 0}
.rt-step{padding:4px 12px;border-radius:999px;border:1px solid #dadce0;color:#5f6368;font-size:.85em}
.rt-step.done{background:#e8f0fe;color:#1a73e8;border-color:#e8f0fe}
.rt-step.now{background:#1a73e8;color:#fff;border-color:#1a73e8;font-weight:600}
</style>
"""


def stepper_html(stage: int) -> str:
    """stage = index into STAGES of the step in progress (len(STAGES) = all done)."""
    parts = []
    for i, name in enumerate(STAGES):
        cls = "done" if i < stage else "now" if i == stage else ""
        mark = "✓ " if i < stage else ""
        parts.append(f'<span class="rt-step {cls}">{mark}{i + 1}. {name}</span>')
    return STEPPER_CSS + '<div class="rt-stepper">' + "".join(parts) + "</div>"


def render_stepper(stage: int, placeholder=None) -> None:
    (placeholder or st).markdown(stepper_html(stage), unsafe_allow_html=True)
