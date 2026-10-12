"""Progress stepper shown above the dispute flow."""
from __future__ import annotations

import streamlit as st

STAGES = ["Filed", "Evidence", "Advocates", "Judge", "Ruling"]

def stepper_html(stage: int) -> str:
    """stage = index into STAGES of the step in progress (len(STAGES) = all done)."""
    parts = []
    for i, name in enumerate(STAGES):
        cls = "done" if i < stage else "now" if i == stage else ""
        mark = "✓ " if i < stage else ""
        parts.append(f'<span class="vp-step {cls}">{mark}{name}</span>')
    return '<div class="vp-steps" aria-label="Progress">' + "".join(parts) + "</div>"


def render_stepper(stage: int, placeholder=None) -> None:
    (placeholder or st).markdown(stepper_html(stage), unsafe_allow_html=True)
