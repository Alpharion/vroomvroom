"""GPS replay map: planned vs actual route."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pydeck as pdk
import streamlit as st

from theme import is_dark

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_trip_geo(dispute_id: str) -> dict[str, Any] | None:
    """Find the case file for a dispute ID (or TC-xx prefix) in the repo's data/ folder.

    Returns None when the frontend can't see data/ (e.g. deployed without it).
    """
    paths = [*_DATA_DIR.glob("*.json"), *(_DATA_DIR / "test_cases").glob("TC-*.json")]
    for path in sorted(paths):
        if path.name.endswith(".expected.json") or path.name == "expected_results.json":
            continue
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if case.get("dispute_ticket", {}).get("dispute_id") == dispute_id or path.name.startswith(dispute_id):
            trip = case.get("trip_data", {})
            return {
                "planned": [[p["lng"], p["lat"]] for p in trip.get("planned_route") or []],
                "actual": [[g["lng"], g["lat"]] for g in case.get("gps_telemetry") or []],
                "pickup": trip.get("pickup_location"),
                "dropoff": trip.get("dropoff_location"),
            }
    return None


def render_route_map(geo: dict[str, Any]) -> None:
    layers = []
    if len(geo["planned"]) >= 2:
        layers.append(pdk.Layer(
            "PathLayer", [{"path": geo["planned"]}], get_path="path",
            get_color=[91, 42, 134], width_min_pixels=4,
        ))
    if len(geo["actual"]) >= 2:
        layers.append(pdk.Layer(
            "PathLayer", [{"path": geo["actual"]}], get_path="path",
            get_color=[224, 53, 111], width_min_pixels=4,
        ))
    points = [
        {"pos": [p["lng"], p["lat"]], "name": p.get("name", label)}
        for label, p in (("Pickup", geo.get("pickup")), ("Drop-off", geo.get("dropoff")))
        if p
    ]
    points += [{"pos": pt, "name": "GPS point"} for pt in geo["actual"]]
    layers.append(pdk.Layer(
        "ScatterplotLayer", points, get_position="pos", get_radius=40,
        get_fill_color=[42, 24, 34], pickable=True,
    ))
    all_pts = geo["planned"] + geo["actual"] or [p["pos"] for p in points]
    if not all_pts:
        st.caption("No GPS data for this case.")
        return
    lng = sum(p[0] for p in all_pts) / len(all_pts)
    lat = sum(p[1] for p in all_pts) / len(all_pts)
    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=lat, longitude=lng, zoom=12.5),
        tooltip={"text": "{name}"},
        map_style="dark" if is_dark() else "light",
    ))
    st.markdown(
        '<div class="vp-legend"><span><i style="background:#5b2a86"></i>Planned route</span>'
        '<span><i style="background:#e0356f"></i>Actual GPS path</span>'
        '<span><i style="background:#2a1822"></i>Pickup, drop-off and GPS points</span></div>',
        unsafe_allow_html=True,
    )
