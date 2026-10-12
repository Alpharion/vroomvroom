"""Policy clause text for tooltips, read from the repo's docs/ folder.

The ruling shows clause IDs (NS-1.3, RD-2.2, ...). This turns each ID into a short,
plain-text version of the clause's Rule so a reader can see what it says.
If docs/ is not deployed with the frontend, the lookup is empty and chips show no popup.
"""
from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

POLICY_PATH = Path(__file__).resolve().parents[1] / "docs" / "ryde_dispute_policy.md"

# ### NS-1.3 — Free Waiting Period  (any dash-like character between ID and title)
_HEADING_RE = re.compile(r"^###\s+([A-Z]+-\d+\.\d+)\s*[‐-―−-]\s*(.+)$")
_NEXT_PART_RE = re.compile(r"\n- \*\*")
# A sentence naming a test case or dispute (e.g. "TC-05 tests this: ...") would leak a test answer.
_TEST_SENTENCE_RE = re.compile(r"[^.!?]*\b(?:TC-\d+|DISP-\d+)\b[^.!?]*[.!?]?\s*")
MAX_CHARS = 420


def _clean(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("|")]  # drop tables
    lines = [("• " + ln.lstrip()[2:]) if ln.lstrip().startswith("- ") else ln for ln in lines]
    text = " ".join(" ".join(lines).split())
    text = text.replace("`", "").replace("**", "")
    text = _TEST_SENTENCE_RE.sub("", text).strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def _rule(body: str) -> str:
    """The text of the clause's '- **Rule:**' bullet, or the start of the body if there is none."""
    start = body.find("- **Rule:**")
    if start == -1:
        return body
    part = body[start + len("- **Rule:**"):]
    end = _NEXT_PART_RE.search(part)
    return part[: end.start()] if end else part


@st.cache_data(show_spinner=False)
def load_clauses() -> dict[str, dict[str, str]]:
    """{clause_id: {"title": ..., "text": ...}}; empty if the policy doc is not available."""
    try:
        lines = POLICY_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    clauses: dict[str, dict[str, str]] = {}
    current: tuple[str, str] | None = None
    body: list[str] = []

    def flush() -> None:
        if current:
            text = _clean(_rule("\n".join(body)))
            if text:
                clauses[current[0]] = {"title": current[1].strip(), "text": text}

    for line in lines:
        m = _HEADING_RE.match(line)
        if m or line.startswith("## "):
            flush()
            current, body = ((m.group(1), m.group(2)) if m else None), []
        elif current:
            body.append(line)
    flush()
    return clauses
