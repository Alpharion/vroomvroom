"""Human review queue and SLA routing (S-1.2, E-1.6)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agents.context import gather_evidence
from app.main import _CASE_INDEX, app
from app.review_queue import ReviewDecision, ReviewQueue
from schemas import DisputeCase, Ruling
from tests.test_api_agents import _fake_chat

client = TestClient(app)


def _ruling(case: DisputeCase, outcome: str, escalated: bool, clauses=("NS-1.8",)) -> Ruling:
    return Ruling(
        dispute_id=case.dispute_ticket.dispute_id,
        outcome=outcome,
        amount_sgd=0.0 if escalated else 5.0,
        confidence=0.5 if escalated else 0.95,
        clauses_cited=list(clauses),
        explanation_rider="r",
        explanation_driver="d",
        escalated=escalated,
        escalation_reason="Missing evidence: gps_telemetry" if escalated else None,
    )


def _remember(queue, case_id, outcome="escalate", escalated=True, **kwargs):
    case = _CASE_INDEX[case_id]
    queue.remember_result(case, _ruling(case, outcome, escalated, **kwargs), gather_evidence(case))
    return case.dispute_ticket.dispute_id


# ---------- queue logic ----------


def test_escalated_ruling_queued_with_normal_sla(review_queue):
    dispute_id = _remember(review_queue, "TC-09")
    [item] = review_queue.list_items()
    assert item["dispute_id"] == dispute_id
    assert item["status"] == "pending"
    assert item["priority"] == "normal"
    assert item["sla_hours"] == 24
    assert item["escalation_reason"] == "Missing evidence: gps_telemetry"
    assert item["suggested_outcome"] is None
    due = datetime.fromisoformat(item["due_at"]) - datetime.fromisoformat(item["created_at"])
    assert due.total_seconds() == 24 * 3600


def test_safety_case_is_high_priority(review_queue):
    _remember(review_queue, "TC-08", clauses=("S-1.1", "S-1.2"))
    [item] = review_queue.list_items()
    assert item["priority"] == "high"
    assert item["priority_reason"] == "Safety incident (S-1.1)"
    assert item["sla_hours"] == 4


def test_high_value_dispute_is_high_priority(review_queue):
    d = _CASE_INDEX["TC-05"].model_dump()
    d["trip_data"]["fare_breakdown"]["actual_fare_sgd"] = 45.0
    case = DisputeCase.model_validate(d)
    review_queue.remember_result(case, _ruling(case, "escalate", True), gather_evidence(case))
    [item] = review_queue.list_items()
    assert item["priority"] == "high"
    assert item["priority_reason"] == "High-value dispute (S$45.00 charged)"


def test_issued_ruling_not_queued(review_queue):
    _remember(review_queue, "DISP-002", outcome="charge_upheld", escalated=False)
    assert review_queue.list_items() == []


def test_queue_order_pending_high_first(review_queue):
    _remember(review_queue, "TC-09")
    _remember(review_queue, "TC-11")
    _remember(review_queue, "TC-08", clauses=("S-1.1",))
    review_queue.decide("DISP-002-T9", ReviewDecision(
        decision="override", outcome="charge_reversed", amount_sgd=5.0))
    order = [(i["dispute_id"], i["status"]) for i in review_queue.list_items()]
    assert order == [
        ("DISP-002-T8", "pending"),
        ("DISP-001-T11", "pending"),
        ("DISP-002-T9", "resolved"),
    ]


def test_no_duplicate_pending_item(review_queue):
    _remember(review_queue, "TC-09")
    _remember(review_queue, "TC-09")
    assert len(review_queue.list_items()) == 1


def test_appeal_suggests_ai_outcome(review_queue):
    _remember(review_queue, "DISP-002", outcome="charge_upheld", escalated=False)
    item = review_queue.appeal("DISP-002")
    assert item["escalation_reason"] == "Appeal: the rider asked for a person to review the AI ruling."
    assert (item["suggested_outcome"], item["suggested_amount_sgd"]) == ("charge_upheld", 5.0)
    assert review_queue.appeal("UNKNOWN") is None


def test_decide_resolves_pending_item(review_queue):
    _remember(review_queue, "TC-09")
    item = review_queue.decide("DISP-002-T9", ReviewDecision(
        decision="override", outcome="charge_reversed", amount_sgd=5.0, note="GPS gap"))
    assert item["status"] == "resolved"
    assert item["decision"]["outcome"] == "charge_reversed"
    assert item["decision"]["note"] == "GPS gap"
    assert "decided_at" in item["decision"]
    assert review_queue.decide("DISP-002-T9", ReviewDecision(
        decision="approve", outcome="no_action", amount_sgd=0)) is None


def test_queue_persists_to_file(tmp_path: Path):
    path = tmp_path / "queue.json"
    _remember(ReviewQueue(store_path=path), "TC-09")
    reloaded = ReviewQueue(store_path=path)
    assert [i["dispute_id"] for i in reloaded.list_items()] == ["DISP-002-T9"]
    assert reloaded.appeal("DISP-002-T9")["dispute_id"] == "DISP-002-T9"  # latest kept


# ---------- API ----------


def _run(dispute_id: str, chat) -> None:
    with patch("agents.advocates.chat", side_effect=chat), \
         patch("agents.judge.chat", side_effect=chat):
        resp = client.post("/api/disputes/resolve", json={"dispute_ticket": {"dispute_id": dispute_id}})
    assert resp.status_code == 200
    list(resp.iter_lines())


def test_api_escalated_run_appears_in_queue_and_can_be_decided():
    _run("TC-08", _fake_chat("safety_check.keyword_hits", "S-1.1"))

    [item] = client.get("/api/review-queue").json()
    assert item["dispute_id"] == "DISP-002-T8"
    assert item["priority"] == "high"
    assert item["ruling"]["outcome"] == "escalate"
    assert {e["tool"] for e in item["evidence"]} >= {"safety_check", "no_show_check"}

    body = {"decision": "override", "outcome": "charge_reversed", "amount_sgd": 5.0, "note": "Threats confirmed"}
    resp = client.post("/api/review-queue/DISP-002-T8/decision", json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    assert client.post("/api/review-queue/DISP-002-T8/decision", json=body).status_code == 404


def test_api_decision_rejects_escalate_outcome():
    _run("TC-08", _fake_chat("safety_check.keyword_hits", "S-1.1"))
    body = {"decision": "approve", "outcome": "escalate", "amount_sgd": 0}
    assert client.post("/api/review-queue/DISP-002-T8/decision", json=body).status_code == 422


def test_api_appeal():
    assert client.post("/api/review-queue/DISP-002/appeal").status_code == 404
    _run("DISP-002", _fake_chat("no_show_check.total_wait_min", "NS-1.4"))
    assert client.get("/api/review-queue").json() == []  # upheld, not escalated
    resp = client.post("/api/review-queue/DISP-002/appeal")
    assert resp.status_code == 200
    assert resp.json()["suggested_outcome"] == "charge_upheld"
    assert len(client.get("/api/review-queue").json()) == 1
