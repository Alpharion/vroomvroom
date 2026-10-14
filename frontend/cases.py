"""Cases the filer can pick from, read from the repo's data/ folder.

The backend resolves a dispute by looking up its dispute_id in the same
folder, so every entry here is something the API can resolve. If data/ is not
deployed with the frontend, a small built-in list is used instead.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_FALLBACK = [
    {
        "dispute_id": "DISP-002",
        "trip_id": "TRIP-2026-09945",
        "dispute_type": "no_show_charge",
        "filed_by": "rider",
        "pickup": "Tiong Bahru Plaza",
        "dropoff": "VivoCity",
        "date": "13 Sep 2026",
        "description": (
            "I was at the pickup point at Tiong Bahru Plaza on time but the driver "
            "never showed up. The app charged me a $5.00 cancellation fee for a "
            "'no-show'. I want the charge reversed."
        ),
    },
    {
        "dispute_id": "DISP-001",
        "trip_id": "TRIP-2026-10012",
        "dispute_type": "route_deviation",
        "filed_by": "rider",
        "pickup": "Tiong Bahru Plaza",
        "dropoff": "VivoCity",
        "date": "20 Sep 2026",
        "description": (
            "The driver took a significantly longer route from Tiong Bahru Plaza to "
            "VivoCity instead of the direct route. I want a refund for the extra distance."
        ),
    },
]


def _pretty_date(iso: str | None) -> str:
    try:
        return datetime.fromisoformat((iso or "")[:10]).strftime("%d %b %Y")
    except ValueError:
        return ""


def _read_case(path: Path) -> dict[str, Any] | None:
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
        ticket, trip = case["dispute_ticket"], case["trip_data"]
    except (OSError, ValueError, KeyError):
        return None
    return {
        "dispute_id": ticket["dispute_id"],
        "trip_id": ticket.get("trip_id") or trip.get("trip_id", ""),
        "dispute_type": ticket["dispute_type"],
        "filed_by": ticket.get("filed_by", "rider"),
        "pickup": trip.get("pickup_location", {}).get("name", "Pickup"),
        "dropoff": trip.get("dropoff_location", {}).get("name", "Drop-off"),
        "date": _pretty_date(trip.get("scheduled_time")),
        "description": ticket.get("description", ""),
    }


_SUPPORTED_TYPES = {"no_show_charge", "route_deviation"}


@st.cache_data(show_spinner=False)
def list_cases() -> list[dict[str, Any]]:
    """The trips a filer can pick: the real data files, one per dispute ID.

    Only files whose dispute_type is supported by the backend are shown, so
    reference fixtures for unsupported types (e.g. fare_dispute) don't appear
    in the filing form.
    """
    cases = [
        c for p in sorted(DATA_DIR.glob("*.json"))
        if not p.name.endswith(".expected.json")
        and (c := _read_case(p))
        and c["dispute_type"] in _SUPPORTED_TYPES
    ]
    return sorted(cases, key=lambda c: c["dispute_id"]) or _FALLBACK


@st.cache_data(show_spinner=False)
def list_test_scenarios() -> list[dict[str, Any]]:
    """Marcus's test cases (TC-xx), for QA. The backend accepts the TC-xx prefix as an ID."""
    out = []
    for path in sorted((DATA_DIR / "test_cases").glob("TC-*.json")):
        case = _read_case(path)
        m = re.match(r"(TC-\d+)-(.*)\.json$", path.name)
        if case and m:
            case["dispute_id"] = m.group(1)
            case["scenario"] = f"{m.group(1)}: {m.group(2).replace('-', ' ')}"
            out.append(case)
    return out


def cases_for_type(dispute_type: str) -> list[dict[str, Any]]:
    return [c for c in list_cases() if c["dispute_type"] == dispute_type]


def case_label(case: dict[str, Any]) -> str:
    """Route, date and trip ID: enough to tell trips apart without showing the filer's text."""
    parts = [f"{case['pickup']} → {case['dropoff']}", case["date"], case["trip_id"]]
    return " · ".join(part for part in parts if part)
