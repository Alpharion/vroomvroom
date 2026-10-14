"""Dispute filing form: who you are, what happened, which trip."""
from __future__ import annotations

import streamlit as st

from cases import case_label, cases_for_type, list_test_scenarios
from state import load_dispute_types

# Wording per role: the same two dispute types, seen from each side of the trip.
TYPE_SUB = {
    "rider": {
        "no_show_charge": "The driver says I did not turn up",
        "route_deviation": "The fare is higher than it should be",
    },
    "driver": {
        "no_show_charge": "The rider says they were at the pickup point",
        "route_deviation": "The rider says the fare is too high",
    },
}

TYPE_HELP = {
    "rider": {
        "no_show_charge": "I was charged a no-show fee",
        "route_deviation": "The driver took a longer route",
    },
    "driver": {
        "no_show_charge": "A rider is disputing my no-show fee",
        "route_deviation": "A rider says I took a longer route",
    },
}


def _role() -> str:
    return st.session_state.get("form_filed_by") or "rider"


def _on_type_change() -> None:
    options = cases_for_type(st.session_state.form_dispute_type)
    st.session_state.form_trip = options[0]["dispute_id"] if options else None


def _selected_case() -> dict | None:
    options = cases_for_type(st.session_state.get("form_dispute_type", ""))
    return next((c for c in options if c["dispute_id"] == st.session_state.get("form_trip")), None)


def render_dispute_form() -> dict | None:
    """Render the dispute filing form. Returns a dispute payload dict on submit."""
    types = [d["value"] for d in load_dispute_types()]
    if "form_dispute_type" not in st.session_state:
        st.session_state.form_dispute_type = types[0]
        _on_type_change()

    st.caption("I am the")
    filer = st.segmented_control(
        "I am the", ["rider", "driver"], default="rider", key="form_filed_by",
        format_func=str.capitalize, label_visibility="collapsed",
    )
    role = _role()
    st.radio(
        "What is this about?", types, key="form_dispute_type", on_change=_on_type_change,
        format_func=lambda v: TYPE_HELP[role].get(v, v),
        captions=[TYPE_SUB[role].get(t, "") for t in types],
    )

    options = cases_for_type(st.session_state.form_dispute_type)
    by_id = {c["dispute_id"]: c for c in options}
    st.selectbox(
        "Which trip?", list(by_id), key="form_trip",
        format_func=lambda i: case_label(by_id[i]),
    )
    st.text_area(
        "What happened, in your words" if role == "rider" else "What happened, from your side",
        height=110, key="form_description",
        placeholder="Tell us what happened, in your own words." if role == "rider" else "Tell us what happened from your side.",
    )
    st.caption("For this demo, the review uses the record we already hold for the trip you pick.")

    scenarios = {c["dispute_id"]: c for c in list_test_scenarios()}
    with st.expander("Advanced (testing)"):
        st.selectbox(
            "Test scenario", [""] + list(scenarios), key="form_scenario",
            format_func=lambda i: "None: use the trip above" if not i else scenarios[i]["scenario"],
            help="Runs one of the team's test cases instead of the trip above.",
        )
        st.text_input(
            "Case ID override", key="form_case_override",
            help="Any backend case ID, e.g. DISP-001-T5. Takes priority over everything above.",
        )

    if st.button("Submit dispute", type="primary", disabled=st.session_state.get("resolving", False)):
        scenario = scenarios.get(st.session_state.get("form_scenario") or "")
        case = scenario or _selected_case()
        override = (st.session_state.get("form_case_override") or "").strip()
        dispute_id = override or (case["dispute_id"] if case else "")
        if not dispute_id:
            st.error("Please pick a trip.")
            return None
        description = (scenario["description"] if scenario else st.session_state.form_description).strip()
        if not description:
            st.error("Please describe what happened.")
            return None
        return {
            "dispute_ticket": {
                "dispute_id": dispute_id,
                "trip_id": case["trip_id"] if case else None,
                "filed_by": scenario["filed_by"] if scenario else (filer or "rider"),
                "dispute_type": scenario["dispute_type"] if scenario else st.session_state.form_dispute_type,
                "description": description,
            }
        }
    return None
