"""FastAPI app for the Ryde Dispute Resolution system.

POST /api/disputes/resolve streams a dispute's resolution as NDJSON: the
real LangGraph agent flow (agents/graph.py), or the stub when
USE_STUB_AGENTS=true.  Stream format: docs/team-brief.md "API contract".
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.graph import dispute_graph
from app.review_queue import ReviewDecision, review_queue
from schemas import AdvocateBrief, AgentLogMessage, Argument, DisputeCase, EvidenceOutput, Ruling
from tools.history_lookup import history_lookup
from tools.no_show_check import compute_no_show_outcome, no_show_check
from tools.route_deviation import compute_route_deviation_outcome, route_deviation

app = FastAPI(title="Ryde Dispute Resolution")

# CORS: allow all origins for local dev only.
# TODO: tighten to the frontend origin before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory -- same resolution as backend/tests/test_tools.py
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_TC_DIR = _DATA_DIR / "test_cases"
_MOCK_AGENT_LOG_PATH = Path(__file__).resolve().parents[2] / "frontend" / "mock_agent_log.json"

_TC_PREFIX_RE = re.compile(r"^(TC-\d+)")


# ---------- Request model ----------


class DisputeTicketRequest(BaseModel):
    """Lightweight dispute-ticket model: only dispute_id is required.

    Other fields are accepted but ignored. We deliberately do NOT validate
    against schemas.DisputeTicket because it requires filed_at and status
    which the frontend does not send.
    """

    dispute_id: str
    trip_id: str | None = None
    filed_by: str | None = None
    dispute_type: str | None = None
    description: str | None = None


class ResolveRequest(BaseModel):
    """Top-level request body: {"dispute_ticket": {"dispute_id": "..."}}."""

    dispute_ticket: DisputeTicketRequest
    # Judge reads the driver's brief first (advocate-order fairness test).
    driver_first: bool = False


# ---------- Case lookup ----------


def _load_case_index() -> dict[str, DisputeCase]:
    """Build a lookup index at startup: dispute_id -> DisputeCase.

    Scans data/*.json (skipping *.expected.json) and
    data/test_cases/TC-*.json. Each case is keyed by its
    dispute_ticket.dispute_id; test cases are also keyed by their
    filename prefix (TC-01 ... TC-10).

    When a test case shares a dispute_id with a real data file
    (e.g. TC-01 has DISP-002), the real data file wins.
    """
    index: dict[str, DisputeCase] = {}

    # First: test cases (lower priority, loaded first so real data overrides)
    if _TC_DIR.is_dir():
        for path in sorted(_TC_DIR.glob("TC-*.json")):
            m = _TC_PREFIX_RE.match(path.name)
            if m is None:
                continue
            tc_key = m.group(1)  # e.g. "TC-01"
            case = DisputeCase.model_validate_json(path.read_text(encoding="utf-8"))
            index[tc_key] = case
            dispute_id = case.dispute_ticket.dispute_id
            if dispute_id not in index:
                index[dispute_id] = case

    # Then: real data files (higher priority -- overwrites TC duplicates)
    for path in sorted(_DATA_DIR.glob("*.json")):
        if path.name.endswith(".expected.json"):
            continue
        case = DisputeCase.model_validate_json(path.read_text(encoding="utf-8"))
        index[case.dispute_ticket.dispute_id] = case

    return index


_CASE_INDEX: dict[str, DisputeCase] = _load_case_index()


def _lookup_case(dispute_id: str) -> DisputeCase:
    """Return the DisputeCase for *dispute_id* or raise 404."""
    case = _CASE_INDEX.get(dispute_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Unknown dispute_id: {dispute_id}")
    return case


# ---------- Mock agent log ----------


def _load_mock_agent_log() -> list[dict[str, Any]]:
    if _MOCK_AGENT_LOG_PATH.is_file():
        return json.loads(_MOCK_AGENT_LOG_PATH.read_text(encoding="utf-8"))
    return []


_MOCK_AGENT_LOG: list[dict[str, Any]] = _load_mock_agent_log()


# ---------- Helpers ----------


def _now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _evidence_summary(evidence: EvidenceOutput) -> str:
    """One-line summary of an EvidenceOutput for the agent log."""
    facts = evidence.facts
    parts: list[str] = []
    for key in sorted(facts):
        val = facts[key]
        if isinstance(val, (list, dict)):
            if isinstance(val, list):
                val_str = f"[{len(val)} items]"
            else:
                val_str = "{...}"
        else:
            val_str = str(val)
        parts.append(f"{key}={val_str}")
    return f"{evidence.tool}: " + ", ".join(parts)


def _build_advocate_brief(
    dispute_id: str,
    side: str,
    evidence: list[EvidenceOutput],
) -> AdvocateBrief:
    """Build a minimal valid AdvocateBrief with placeholder text."""
    tool_refs = [e.tool for e in evidence]
    brief = AdvocateBrief(
        dispute_id=dispute_id,
        side=side,
        position=f"[stub] {side.capitalize()} advocate position placeholder",
        arguments=[
            Argument(
                point=f"[stub] Placeholder argument for {side} advocate. "
                f"Evidence gathered: {', '.join(tool_refs)}.",
                evidence_refs=tool_refs if tool_refs else ["history_lookup"],
                clauses=["NS-1.6"] if side == "driver" else ["NS-1.7"],
            ),
        ],
        weaknesses_acknowledged=["[stub] Placeholder weakness"],
    )
    return brief


def _build_ruling(
    dispute_id: str,
    outcome: str,
    amount_sgd: float,
    clauses_cited: list[str],
    conduct_flag: bool,
    missing_evidence: list[str],
) -> Ruling:
    """Build a Ruling from the real outcome formula output."""
    escalated = outcome == "escalate"
    confidence = 0.5 if escalated else 0.9
    escalation_reason = None
    if escalated:
        if missing_evidence:
            escalation_reason = "Missing evidence: " + ", ".join(missing_evidence)
        else:
            escalation_reason = "[stub] Escalation required"
    ruling = Ruling(
        dispute_id=dispute_id,
        outcome=outcome,
        amount_sgd=amount_sgd,
        confidence=confidence,
        clauses_cited=clauses_cited,
        explanation_rider="[stub] Placeholder explanation for rider.",
        explanation_driver="[stub] Placeholder explanation for driver.",
        conduct_flag=conduct_flag,
        escalated=escalated,
        escalation_reason=escalation_reason,
    )
    return ruling

# ---------- Stub stream (USE_STUB_AGENTS=true) ----------


async def _stub_stream(case: DisputeCase):
    """USE_STUB_AGENTS=true: real evidence and outcome formulas, mocked
    advocate/Judge messages.  For UI work without spending ADP credits,
    and as a demo fallback if ADP is down."""
    seq = 0
    try:
        # --- Step 1: Real evidence ---
        evidence_outputs: list[EvidenceOutput] = []
    
        history = history_lookup(case)
        evidence_outputs.append(history)
        seq += 1
        yield json.dumps(AgentLogMessage(
            seq=seq,
            agent="system",
            type="evidence",
            content=_evidence_summary(history),
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json")) + "\n"
        await asyncio.sleep(0.4)
    
        yield json.dumps({
            "type": "evidence_data",
            "data": history.model_dump(mode="json"),
        }) + "\n"
        await asyncio.sleep(0.4)
    
        dispute_type = case.dispute_ticket.dispute_type
        if dispute_type == "no_show_charge":
            tool_evidence = no_show_check(case)
        elif dispute_type == "route_deviation":
            tool_evidence = route_deviation(case)
        else:
            tool_evidence = None
    
        if tool_evidence is not None:
            evidence_outputs.append(tool_evidence)
            seq += 1
            yield json.dumps(AgentLogMessage(
                seq=seq,
                agent="system",
                type="evidence",
                content=_evidence_summary(tool_evidence),
                timestamp=datetime.now(timezone.utc),
            ).model_dump(mode="json")) + "\n"
            await asyncio.sleep(0.4)
    
            yield json.dumps({
                "type": "evidence_data",
                "data": tool_evidence.model_dump(mode="json"),
            }) + "\n"
            await asyncio.sleep(0.4)
    
        # --- Step 2: Mock agent messages (skip system entries) ---
        for entry in _MOCK_AGENT_LOG:
            if entry.get("agent") == "system":
                continue
            seq += 1
            entry_out = {
                "seq": seq,
                "agent": entry["agent"],
                "type": entry["type"],
                "content": entry["content"],
                "timestamp": _now_iso(),
            }
            yield json.dumps(entry_out) + "\n"
            await asyncio.sleep(0.4)
    
        # --- Step 3: Mock briefs ---
        for side in ("rider", "driver"):
            brief = _build_advocate_brief(
                dispute_id=case.dispute_ticket.dispute_id,
                side=side,
                evidence=evidence_outputs,
            )
            yield json.dumps({
                "type": "brief_data",
                "data": brief.model_dump(mode="json"),
            }) + "\n"
            await asyncio.sleep(0.4)
    
        # --- Step 4: Ruling from real outcome formula ---
        if dispute_type == "no_show_charge":
            facts = no_show_check(case).facts
            outcome, amount, clauses, conduct = compute_no_show_outcome(facts)
            missing = facts.get("missing_evidence", [])
        else:
            facts = route_deviation(case).facts
            outcome, amount, clauses, conduct = compute_route_deviation_outcome(facts)
            missing = facts.get("missing_evidence", [])
    
        ruling = _build_ruling(
            dispute_id=case.dispute_ticket.dispute_id,
            outcome=outcome,
            amount_sgd=amount,
            clauses_cited=clauses,
            conduct_flag=conduct,
            missing_evidence=missing,
        )
        review_queue.remember_result(case, ruling, evidence_outputs)
        yield json.dumps({
            "type": "ruling_data",
            "data": ruling.model_dump(mode="json"),
        }) + "\n"
        await asyncio.sleep(0.4)
    
    except Exception as e:
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"


# ---------- Real agent stream (LangGraph) ----------


def _line(obj: dict[str, Any]) -> str:
    return json.dumps(obj) + "\n"


def _log(seq: int, agent: str, type_: str, content: str) -> str:
    return _line(AgentLogMessage(
        seq=seq,
        agent=agent,
        type=type_,
        content=content,
        timestamp=datetime.now(timezone.utc),
    ).model_dump(mode="json"))


def _ruling_summary(ruling: Ruling) -> str:
    text = (
        f"Ruling: {ruling.outcome}, S${ruling.amount_sgd:.2f} "
        f"(confidence {ruling.confidence:.2f}). "
        f"Clauses: {', '.join(ruling.clauses_cited)}."
    )
    if ruling.escalated:
        text += f" Escalated: {ruling.escalation_reason}."
    return text


async def _agent_stream(case: DisputeCase, driver_first: bool):
    """Stream the LangGraph run node by node in the agreed NDJSON format."""
    seq = 0
    evidence: list[EvidenceOutput] = []
    try:
        async for update in dispute_graph.astream(
            {"case": case, "driver_first": driver_first},
            stream_mode="updates",
        ):
            for node, out in update.items():
                out = out or {}
                if node == "gather_evidence":
                    evidence = out["evidence"]
                    for ev in evidence:
                        seq += 1
                        yield _log(seq, "system", "evidence", _evidence_summary(ev))
                        yield _line({"type": "evidence_data", "data": ev.model_dump(mode="json")})
                elif node in ("rider_advocate", "driver_advocate"):
                    brief = out["rider_brief" if node == "rider_advocate" else "driver_brief"]
                    seq += 1
                    yield _log(seq, node, "argument", brief.position)
                    for arg in brief.arguments:
                        seq += 1
                        yield _log(seq, node, "argument", arg.point)
                    yield _line({"type": "brief_data", "data": brief.model_dump(mode="json")})
                elif node == "judge":
                    ruling = out["ruling"]
                    review_queue.remember_result(case, ruling, evidence)
                    seq += 1
                    yield _log(seq, "judge", "ruling", _ruling_summary(ruling))
                    yield _line({"type": "ruling_data", "data": ruling.model_dump(mode="json")})
                elif node == "human_review":
                    seq += 1
                    yield _log(seq, "system", "ruling", "Routed to the human review queue.")
    except Exception as e:
        yield _line({"type": "error", "content": str(e)})


# ---------- Streaming endpoint ----------


@app.post("/api/disputes/resolve")
async def resolve_dispute(req: ResolveRequest):
    """Stream agent log messages and structured data as NDJSON.

    Runs the real agents (LangGraph) unless ``USE_STUB_AGENTS=true``.
    """
    case = _lookup_case(req.dispute_ticket.dispute_id)
    if os.environ.get("USE_STUB_AGENTS", "").lower() == "true":
        stream = _stub_stream(case)
    else:
        stream = _agent_stream(case, req.driver_first)
    # Stop proxies and gateways from buffering the stream, which would hold
    # back each agent message until the whole hearing has finished.
    return StreamingResponse(
        stream,
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- Human review queue ----------


@app.get("/api/review-queue")
def list_review_queue():
    """Escalated and appealed disputes: pending first, high priority first."""
    return review_queue.list_items()


@app.post("/api/review-queue/{dispute_id}/decision")
def decide_review(dispute_id: str, decision: ReviewDecision):
    """A reviewer approves or overrides the pending item for *dispute_id*."""
    item = review_queue.decide(dispute_id, decision)
    if item is None:
        raise HTTPException(status_code=404, detail=f"No pending review for {dispute_id}")
    return item


@app.post("/api/review-queue/{dispute_id}/appeal")
def appeal_ruling(dispute_id: str):
    """The filer asks for a person to review the latest AI ruling."""
    item = review_queue.appeal(dispute_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"No ruling yet for {dispute_id}")
    return item


@app.get("/health")
def health():
    return {"status": "ok"}
