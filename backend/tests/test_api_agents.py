"""Tests for the real agent stream of POST /api/disputes/resolve (LangGraph).

LLM calls are replaced with canned replies, so no ADP credits are used.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agents.llm import LLMError, LLMResult
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _use_real_agents(monkeypatch):
    monkeypatch.delenv("USE_STUB_AGENTS", raising=False)


def _result(payload: dict) -> LLMResult:
    return LLMResult(
        text=json.dumps(payload), input_tokens=None, output_tokens=None,
        total_tokens=1, cached=False,
    )


def _fake_chat(evidence_ref: str, clause: str, judge_findings: dict | None = None,
               seen: list | None = None):
    async def chat(agent, system_prompt, user_message, **kwargs):
        if seen is not None:
            seen.append((agent, user_message))
        if agent == "judge":
            return _result({
                "rider_requested_detour": None,
                "traffic_justified": None,
                **(judge_findings or {}),
                "confidence": 0.95,
                "clauses_cited": [clause],
                "explanation_rider": "For the rider.",
                "explanation_driver": "For the driver.",
            })
        side = agent.removesuffix("_advocate")
        return _result({
            "dispute_id": "ignored",
            "side": side,
            "position": f"{side} position",
            "arguments": [{
                "point": f"{side} point",
                "evidence_refs": [evidence_ref],
                "clauses": [clause],
            }],
            "weaknesses_acknowledged": [],
        })
    return chat


def _post(dispute_id: str, chat, **body) -> list[dict]:
    with patch("agents.advocates.chat", side_effect=chat), \
         patch("agents.judge.chat", side_effect=chat):
        resp = client.post(
            "/api/disputes/resolve",
            json={"dispute_ticket": {"dispute_id": dispute_id}, **body},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(raw) for raw in resp.iter_lines() if raw]


def test_disp002_real_flow_stream():
    lines = _post("DISP-002", _fake_chat("no_show_check.total_wait_min", "NS-1.4"))
    types = [line["type"] for line in lines]

    evidence = [l["data"]["tool"] for l in lines if l["type"] == "evidence_data"]
    assert evidence == ["history_lookup", "safety_check", "no_show_check", "fare_validate"]
    assert sorted(l["data"]["side"] for l in lines if l["type"] == "brief_data") == ["driver", "rider"]
    assert {l["agent"] for l in lines if l["type"] == "argument"} == {"rider_advocate", "driver_advocate"}

    assert types[-1] == "ruling_data"
    ruling = lines[-1]["data"]
    assert ruling["outcome"] == "charge_upheld"
    assert ruling["amount_sgd"] == 5.0
    assert ruling["dispute_id"] == "DISP-002"

    seqs = [l["seq"] for l in lines if "seq" in l]
    assert seqs == list(range(1, len(seqs) + 1))


def test_tc08_safety_routed_to_human_review():
    lines = _post("TC-08", _fake_chat("safety_check.keyword_hits", "S-1.1"))
    ruling = next(l["data"] for l in lines if l["type"] == "ruling_data")
    assert ruling["outcome"] == "escalate"
    assert ruling["escalated"] is True
    assert lines[-1]["content"] == "Routed to the human review queue."


def test_tc05_judge_findings_decide_refund():
    chat = _fake_chat(
        "route_deviation.deviation_pct", "RD-2.6",
        judge_findings={"rider_requested_detour": False, "traffic_justified": False},
    )
    ruling = _post("TC-05", chat)[-1]["data"]
    assert (ruling["outcome"], ruling["amount_sgd"]) == ("refund", 1.07)


def test_driver_first_reaches_the_judge():
    seen: list = []
    _post("DISP-002", _fake_chat("no_show_check.total_wait_min", "NS-1.4", seen=seen),
          driver_first=True)
    judge_msg = json.loads(next(msg for agent, msg in seen if agent == "judge"))
    keys = list(judge_msg)
    assert keys.index("driver_brief") < keys.index("rider_brief")


def test_llm_failure_streams_error_line():
    async def failing_chat(agent, system_prompt, user_message, **kwargs):
        raise LLMError("App key invalid")

    lines = _post("DISP-002", failing_chat)
    assert lines[-1] == {"type": "error", "content": "App key invalid"}
    assert not any(l["type"] == "ruling_data" for l in lines)


# ---------- The filer's form entries reach the agents ----------


def _advocate_case_summary(seen: list) -> dict:
    msg = next(m for agent, m in seen if agent == "rider_advocate")
    return json.loads(msg)["case_summary"]["dispute_ticket"]


def test_form_description_and_role_reach_the_agents():
    seen: list = []
    typed = "I waited outside the main entrance the whole time and nobody came."
    _post("DISP-002", _fake_chat("no_show_check.total_wait_min", "NS-1.4", seen=seen),
          **{"dispute_ticket": {"dispute_id": "DISP-002", "description": typed, "filed_by": "driver"}})
    ticket = _advocate_case_summary(seen)
    assert ticket["description"] == typed
    assert ticket["filed_by"] == "driver"


def test_typed_threat_escalates_as_safety_incident(review_queue):
    """DISP-002's stored text has no threat; the filer types one in the form."""
    typed = "The driver threatened me when I complained about the fee."
    lines = _post("DISP-002", _fake_chat("no_show_check.total_wait_min", "NS-1.4"),
                  **{"dispute_ticket": {"dispute_id": "DISP-002", "description": typed}})
    safety = next(l["data"] for l in lines if l["type"] == "evidence_data" and l["data"]["tool"] == "safety_check")
    assert safety["facts"]["safety_incident"] is True
    assert safety["facts"]["flagged_messages"][-1] == {"sender": "dispute_description", "content": typed}
    ruling = next(l["data"] for l in lines if l["type"] == "ruling_data")
    assert ruling["outcome"] == "escalate"
    [item] = review_queue.list_items()
    assert item["description"] == typed
    assert item["priority"] == "high"


def test_blank_form_description_keeps_stored_text():
    from app.main import _CASE_INDEX

    seen: list = []
    _post("DISP-002", _fake_chat("no_show_check.total_wait_min", "NS-1.4", seen=seen),
          **{"dispute_ticket": {"dispute_id": "DISP-002", "description": "   "}})
    stored = _CASE_INDEX["DISP-002"].dispute_ticket.description
    assert _advocate_case_summary(seen)["description"] == stored


def test_form_entries_do_not_change_the_stored_case():
    from app.main import _CASE_INDEX

    before = _CASE_INDEX["DISP-002"].dispute_ticket.description
    _post("DISP-002", _fake_chat("no_show_check.total_wait_min", "NS-1.4"),
          **{"dispute_ticket": {"dispute_id": "DISP-002", "description": "Something else entirely."}})
    assert _CASE_INDEX["DISP-002"].dispute_ticket.description == before


def test_invalid_form_role_rejected():
    resp = client.post("/api/disputes/resolve",
                       json={"dispute_ticket": {"dispute_id": "DISP-002", "filed_by": "passenger"}})
    assert resp.status_code == 422


def test_typed_claim_checked_in_ruling_data():
    """The rider types 'I paid $50'; the ruling reports it against the record."""
    base_chat = _fake_chat("no_show_check.total_wait_min", "NS-1.4")
    seen: list = []

    async def chat(agent, system_prompt, user_message, **kwargs):
        seen.append((agent, user_message))
        result = await base_chat(agent, system_prompt, user_message)
        if agent != "judge":
            return result
        reply = json.loads(result.text)
        reply["claim_checks"] = [{
            "claim": "Paid $50", "record": "Charged S$5.00 (cancellation fee)",
            "evidence_refs": ["fare_validate.actual_fare_sgd"], "verdict": "contradicted",
        }]
        return _result(reply)

    typed = "The driver never came and I paid $50 for nothing."
    lines = _post("DISP-002", chat, **{"dispute_ticket": {"dispute_id": "DISP-002", "description": typed}})
    judge_msg = json.loads(next(m for a, m in seen if a == "judge"))
    assert judge_msg["case_summary"]["dispute_ticket"]["description"] == typed
    ruling = lines[-1]["data"]
    assert ruling["amount_sgd"] == 5.0
    assert ruling["claim_checks"][0]["verdict"] == "contradicted"
