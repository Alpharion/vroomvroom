"""Human review queue: escalated cases waiting for a person to decide.

Proposed backend contract (not built yet; this module falls back to a
session-local queue until it exists):
    GET  /api/review-queue                       -> list[QueueItem]
    POST /api/review-queue/{dispute_id}/decision -> QueueItem
         body: {"decision": "approve" | "override", "outcome": str,
                "amount_sgd": float, "note": str}
QueueItem = {dispute_id, dispute_type, filed_by, description, priority
("high" | "normal"), status ("pending" | "resolved"), escalation_reason,
suggested_outcome, suggested_amount_sgd, ruling (Ruling), evidence
(list[EvidenceOutput]), decision (null | {decision, outcome, amount_sgd,
note, decided_at})}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import streamlit as st

from state import BACKEND_URL, MOCK_DIR

_LOCAL_KEY = "review_queue_local"
_SEEDED_KEY = "review_queue_seeded"
_TIMEOUT = httpx.Timeout(3.0)


def _local() -> list[dict[str, Any]]:
    return st.session_state.setdefault(_LOCAL_KEY, [])


def seed_samples() -> None:
    """Add the sample escalated cases once per session (demo mode)."""
    if st.session_state.get(_SEEDED_KEY):
        return
    with open(MOCK_DIR / "mock_review_queue.json") as f:
        samples = json.load(f)
    known = {i["dispute_id"] for i in _local()}
    _local().extend(s for s in samples if s["dispute_id"] not in known)
    st.session_state[_SEEDED_KEY] = True


def _priority(ruling: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    safety = any(c.startswith("S-") for c in ruling.get("clauses_cited") or []) or any(
        e.get("tool") == "safety_check" and e.get("facts", {}).get("safety_incident")
        for e in evidence
    )
    return "high" if safety else "normal"


def record_escalation(payload: dict[str, Any], ruling: dict[str, Any], evidence: list[dict[str, Any]]) -> None:
    """Add an escalated ruling from a UI run to the local queue (no duplicates)."""
    if not ruling.get("escalated"):
        return
    ticket = (payload or {}).get("dispute_ticket", {})
    dispute_id = ruling.get("dispute_id") or ticket.get("dispute_id")
    if any(i["dispute_id"] == dispute_id and i["status"] == "pending" for i in _local()):
        return
    _local().append(
        {
            "dispute_id": dispute_id,
            "dispute_type": ticket.get("dispute_type"),
            "filed_by": ticket.get("filed_by"),
            "description": ticket.get("description"),
            "priority": _priority(ruling, evidence),
            "status": "pending",
            "escalation_reason": ruling.get("escalation_reason"),
            "suggested_outcome": None,
            "suggested_amount_sgd": None,
            "ruling": ruling,
            "evidence": evidence,
            "decision": None,
        }
    )


def record_appeal(payload: dict[str, Any], ruling: dict[str, Any], evidence: list[dict[str, Any]]) -> None:
    """A filer asks for a person to look at an AI ruling. The AI outcome becomes the
    suggestion, so the reviewer can approve it or override it."""
    ticket = (payload or {}).get("dispute_ticket", {})
    dispute_id = ruling.get("dispute_id") or ticket.get("dispute_id")
    if any(i["dispute_id"] == dispute_id and i["status"] == "pending" for i in _local()):
        return
    _local().append(
        {
            "dispute_id": dispute_id,
            "dispute_type": ticket.get("dispute_type"),
            "filed_by": ticket.get("filed_by"),
            "description": ticket.get("description"),
            "priority": _priority(ruling, evidence),
            "status": "pending",
            "escalation_reason": f"Appeal: the {ticket.get('filed_by') or 'filer'} asked for a person to review the AI ruling.",
            "suggested_outcome": ruling.get("outcome"),
            "suggested_amount_sgd": ruling.get("amount_sgd"),
            "ruling": ruling,
            "evidence": evidence,
            "decision": None,
        }
    )


def list_queue() -> tuple[list[dict[str, Any]], str]:
    """Return (items, source) where source is "backend" or "local"."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/review-queue", timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.json(), "backend"
    except (httpx.HTTPError, ValueError):
        pass
    return _local(), "local"


def submit_decision(
    item: dict[str, Any], source: str, decision: str, outcome: str, amount_sgd: float, note: str
) -> None:
    """Record the reviewer's decision. Raises RuntimeError if the backend rejects it."""
    body = {"decision": decision, "outcome": outcome, "amount_sgd": amount_sgd, "note": note}
    if source == "backend":
        try:
            resp = httpx.post(
                f"{BACKEND_URL}/api/review-queue/{item['dispute_id']}/decision",
                json=body,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Could not save the decision: {e}") from e
        return
    item["status"] = "resolved"
    item["decision"] = {**body, "decided_at": datetime.now(timezone.utc).isoformat()}
