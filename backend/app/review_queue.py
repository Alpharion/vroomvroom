"""Human review queue (S-1.2, E-1.6) with SLA routing.

Escalated rulings and rider/driver appeals wait here for a person to approve
or override.  The item shape follows the contract in
frontend/review_queue.py, plus SLA fields (priority_reason, sla_hours,
created_at, due_at).

Priority: safety incidents and high-value disputes are "high" with a short
SLA; everything else is "normal".  The queue lists pending items first,
high priority first, then by due time.

Stored in memory and mirrored to backend/.review_queue.json so it survives a
restart.  Fine for the demo; a real deployment would use a database.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.policy_constants import (
    HIGH_VALUE_DISPUTE_SGD,
    SLA_HOURS_HIGH,
    SLA_HOURS_NORMAL,
)
from schemas import DisputeCase, EvidenceOutput, Ruling

_STORE_PATH = Path(__file__).resolve().parents[1] / ".review_queue.json"

# A reviewer decides the final outcome, so "escalate" is not a valid choice.
ReviewOutcome = Literal[
    "refund", "compensation", "no_action", "charge_upheld", "charge_reversed",
]


class ReviewDecision(BaseModel):
    decision: Literal["approve", "override"]
    outcome: ReviewOutcome
    amount_sgd: float = Field(ge=0)
    note: str = ""


class ReviewQueue:
    def __init__(self, store_path: Path | None = _STORE_PATH):
        self._store_path = store_path
        self._items: list[dict[str, Any]] = []
        # Latest ruling per dispute, so an appeal can reference it by ID.
        self._latest: dict[str, dict[str, Any]] = {}
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        if self._store_path is None or not self._store_path.is_file():
            return
        data = json.loads(self._store_path.read_text(encoding="utf-8"))
        self._items = data.get("items", [])
        self._latest = data.get("latest", {})

    def _save(self) -> None:
        if self._store_path is None:
            return
        self._store_path.write_text(
            json.dumps({"items": self._items, "latest": self._latest}, indent=2),
            encoding="utf-8",
        )

    # ---------- recording ----------

    def remember_result(
        self, case: DisputeCase, ruling: Ruling, evidence: list[EvidenceOutput],
    ) -> None:
        """Record a finished run; escalated rulings join the queue."""
        dispute_id = case.dispute_ticket.dispute_id
        self._latest[dispute_id] = {
            "ticket": _ticket(case),
            "ruling": ruling.model_dump(mode="json"),
            "evidence": [e.model_dump(mode="json") for e in evidence],
        }
        if ruling.escalated:
            self._add(dispute_id, reason=ruling.escalation_reason, suggested=None)
        self._save()

    def appeal(self, dispute_id: str) -> dict[str, Any] | None:
        """Queue an AI ruling for human review at the filer's request.

        Returns the queue item, or None if no ruling is known for the ID.
        The AI outcome becomes the suggestion the reviewer approves or
        overrides.
        """
        latest = self._latest.get(dispute_id)
        if latest is None:
            return None
        ruling = latest["ruling"]
        filed_by = latest["ticket"].get("filed_by") or "filer"
        item = self._add(
            dispute_id,
            reason=f"Appeal: the {filed_by} asked for a person to review the AI ruling.",
            suggested=(ruling["outcome"], ruling["amount_sgd"]),
        )
        self._save()
        return item

    def _add(
        self,
        dispute_id: str,
        reason: str | None,
        suggested: tuple[str, float] | None,
    ) -> dict[str, Any]:
        existing = self._pending(dispute_id)
        if existing is not None:
            return existing

        latest = self._latest[dispute_id]
        ticket, ruling, evidence = latest["ticket"], latest["ruling"], latest["evidence"]
        priority, priority_reason = _priority(ruling, evidence)
        sla_hours = SLA_HOURS_HIGH if priority == "high" else SLA_HOURS_NORMAL
        created_at = datetime.now(timezone.utc)

        item = {
            "dispute_id": dispute_id,
            "dispute_type": ticket.get("dispute_type"),
            "filed_by": ticket.get("filed_by"),
            "description": ticket.get("description"),
            "priority": priority,
            "priority_reason": priority_reason,
            "sla_hours": sla_hours,
            "created_at": created_at.isoformat(),
            "due_at": (created_at + timedelta(hours=sla_hours)).isoformat(),
            "status": "pending",
            "escalation_reason": reason,
            "suggested_outcome": suggested[0] if suggested else None,
            "suggested_amount_sgd": suggested[1] if suggested else None,
            "ruling": ruling,
            "evidence": evidence,
            "decision": None,
        }
        self._items.append(item)
        return item

    # ---------- reviewing ----------

    def list_items(self) -> list[dict[str, Any]]:
        """Pending first, high priority first, then earliest due."""
        return sorted(
            self._items,
            key=lambda i: (i["status"] != "pending", i["priority"] != "high", i["due_at"]),
        )

    def decide(self, dispute_id: str, decision: ReviewDecision) -> dict[str, Any] | None:
        """Resolve the pending item for *dispute_id*; None if there is none."""
        item = self._pending(dispute_id)
        if item is None:
            return None
        item["status"] = "resolved"
        item["decision"] = {
            **decision.model_dump(),
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        return item

    def _pending(self, dispute_id: str) -> dict[str, Any] | None:
        return next(
            (i for i in self._items if i["dispute_id"] == dispute_id and i["status"] == "pending"),
            None,
        )


def _ticket(case: DisputeCase) -> dict[str, Any]:
    t = case.dispute_ticket
    return {
        "dispute_type": t.dispute_type,
        "filed_by": t.filed_by,
        "description": t.description,
    }


def _priority(
    ruling: dict[str, Any], evidence: list[dict[str, Any]],
) -> tuple[Literal["high", "normal"], str]:
    """SLA routing: safety first, then high-value disputes."""
    facts = {e["tool"]: e["facts"] for e in evidence}
    if facts.get("safety_check", {}).get("safety_incident") or any(
        c.startswith("S-") for c in ruling.get("clauses_cited", [])
    ):
        return "high", "Safety incident (S-1.1)"
    fare = facts.get("fare_validate", {}).get("actual_fare_sgd")
    if fare is not None and fare >= HIGH_VALUE_DISPUTE_SGD:
        return "high", f"High-value dispute (S${fare:.2f} charged)"
    return "normal", "Standard"


review_queue = ReviewQueue()
