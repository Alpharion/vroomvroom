"""UI state helpers for loading mock data and calling the backend API."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import streamlit as st
import httpx

MOCK_DIR = Path(__file__).resolve().parent

# Demo mode replays recorded hearings and never reads what the filer types,
# so it is off unless secrets.toml or DEMO_MODE turns it on.
try:
    BACKEND_URL = st.secrets.get("backend_url", "http://localhost:8000")
    DEFAULT_DEMO_MODE = bool(st.secrets.get("demo_mode", False))
except Exception:
    BACKEND_URL = "http://localhost:8000"
    DEFAULT_DEMO_MODE = False

# Environment variables win over secrets.toml, so a deployed container can be
# configured without a secrets file (see Dockerfile.frontend).
BACKEND_URL = os.environ.get("BACKEND_URL", BACKEND_URL).rstrip("/")
if "DEMO_MODE" in os.environ:
    DEFAULT_DEMO_MODE = os.environ["DEMO_MODE"].strip().lower() == "true"


def load_mock_ruling() -> dict[str, Any]:
    with open(MOCK_DIR / "mock_ruling.json") as f:
        return json.load(f)


def load_mock_agent_log() -> list[dict[str, Any]]:
    with open(MOCK_DIR / "mock_agent_log.json") as f:
        return json.load(f)


def load_mock_evidence() -> list[dict[str, Any]]:
    with open(MOCK_DIR / "mock_evidence.json") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_dispute_types() -> list[dict[str, Any]]:
    """Return selectable dispute types for the filing form."""
    return [
        {"value": "no_show_charge", "label": "No-Show Charge"},
        {"value": "route_deviation", "label": "Route Deviation"},
    ]


class BackendError(Exception):
    """Raised when the backend is unreachable or returns an invalid response."""


DEMO_DIR = MOCK_DIR / "demo_cases"


def _demo_case(dispute_id: str | None) -> dict[str, Any] | None:
    """The simulated hearing for a case ID, built by scripts/build_demo_cases.py, or None."""
    if not dispute_id:
        return None
    path = DEMO_DIR / f"{dispute_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mock_stream(payload: dict[str, Any] | None = None):
    """Replay a simulated hearing in the same event order as the real backend: evidence
    first, then each advocate and its brief, then the Judge and the ruling.

    The case comes from demo_cases/<dispute_id>.json (evidence and outcome from the real
    tools). DISP-002 and unknown IDs use the hand-written mock case."""
    import random
    import time

    dispute_id = ((payload or {}).get("dispute_ticket") or {}).get("dispute_id")
    case = _demo_case(dispute_id)
    if case is None or dispute_id == "DISP-002":
        for ev in load_mock_evidence():
            time.sleep(0.5)
            yield {"type": "evidence_data", "data": ev}
        for msg in load_mock_agent_log():
            if msg.get("agent") == "system" and msg.get("type") == "evidence":
                continue  # shown as readable evidence lines built from evidence_data
            time.sleep(random.uniform(0.6, 1.2))
            yield msg
        yield {"type": "ruling_data", "data": load_mock_ruling()}
        return

    for ev in case["evidence"]:
        time.sleep(0.5)
        yield {"type": "evidence_data", "data": ev}
    briefs = {b["side"]: b for b in case["briefs"]}
    for msg in case["log"]:
        time.sleep(random.uniform(0.6, 1.2))
        if msg.get("agent") == "_brief":
            yield {"type": "brief_data", "data": briefs[msg["side"]]}
        else:
            yield msg
    yield {"type": "ruling_data", "data": case["ruling"]}


def stream_events(dispute_payload: dict[str, Any], demo_mode: bool = True):
    """Yield every stream event as a dict.

    Event shapes (see docs/team-brief.md "API contract"): agent log lines
    (have an ``agent`` key), ``evidence_data``, ``brief_data``, ``ruling_data``
    and ``error``.

    In demo mode, replays the mock log with simulated delays. Otherwise streams
    NDJSON from the backend and raises BackendError on any failure (including an
    ``error`` event), so the UI never passes off mock data as a real ruling.
    """
    if demo_mode:
        yield from _mock_stream(dispute_payload)
        return

    timeout = httpx.Timeout(connect=5.0, read=180.0, write=10.0, pool=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{BACKEND_URL}/api/disputes/resolve",
                json=dispute_payload,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("type") == "error":
                        raise BackendError(f"Backend error: {event.get('content', 'unknown')}.")
                    yield event
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise BackendError("Unknown dispute ID: the backend has no case with that ID.") from e
        raise BackendError(f"Backend returned HTTP {e.response.status_code}.") from e
    except httpx.TimeoutException as e:
        raise BackendError("The backend took too long to respond.") from e
    except httpx.HTTPError as e:
        raise BackendError(f"Could not reach the backend at {BACKEND_URL}.") from e
    except json.JSONDecodeError as e:
        raise BackendError("Backend sent a malformed message.") from e
