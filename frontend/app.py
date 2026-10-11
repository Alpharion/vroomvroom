"""Ryde Track — Dispute Resolution Frontend (Streamlit)

Run:
    cd frontend
    pip install -r requirements.txt
    streamlit run app.py

Builds against mock data by default. When the backend is running and reachable,
the courtroom log streams real agent messages from the FastAPI endpoint.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make frontend/ importable when running `streamlit run app.py` from frontend/
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from state import (
    DEFAULT_DEMO_MODE,
    BackendError,
    load_mock_agent_log,
    load_mock_evidence,
    load_mock_ruling,
    stream_events,
)
from components.dispute_form import render_dispute_form
from components.courtroom_log import render_courtroom_log, _message_html
from components.ruling_cards import render_ruling_card, render_evidence_card

st.set_page_config(
    page_title="Ryde Track — Dispute Resolution",
    page_icon="⚖️",
    layout="wide",
)


def main() -> None:
    st.title("Ryde Track")
    st.caption("Multi-Agent Autonomous Dispute Resolution")

    # --- Session state init ---
    if "demo_mode" not in st.session_state:
        st.session_state.demo_mode = DEFAULT_DEMO_MODE
    if "error" not in st.session_state:
        st.session_state.error = None
    if "agent_log" not in st.session_state:
        st.session_state.agent_log = []
    if "ruling" not in st.session_state:
        st.session_state.ruling = None
    if "evidence" not in st.session_state:
        st.session_state.evidence = []
    if "resolving" not in st.session_state:
        st.session_state.resolving = False

    st.sidebar.toggle("Demo mode (simulated data)", key="demo_mode")
    if st.session_state.get("demo_mode"):
        st.info("Demo mode: agent messages, evidence and rulings are simulated, not live.")

    # --- Step 1: Dispute filing form (submitting starts the resolution) ---
    submitted_payload = render_dispute_form()
    if submitted_payload is not None:
        st.session_state.payload = submitted_payload
        st.session_state.resolving = True
        st.session_state.agent_log = []
        st.session_state.evidence = []
        st.session_state.ruling = None
        st.rerun()

    col_mock, col_clear, _ = st.columns([1, 1, 2])
    with col_mock:
        if st.button("Load Mock Data", disabled=st.session_state.resolving):
            st.session_state.agent_log = load_mock_agent_log()
            st.session_state.evidence = load_mock_evidence()
            st.session_state.ruling = load_mock_ruling()
    with col_clear:
        if st.button("Clear", disabled=st.session_state.resolving):
            st.session_state.agent_log = []
            st.session_state.evidence = []
            st.session_state.ruling = None

    # --- Step 2: Resolve (stream agents one-by-one) ---
    if st.session_state.resolving:
        st.subheader("Courtroom")
        st.caption("Agents build their cases in real time")

        courtroom_placeholder = st.empty()
        status_placeholder = st.empty()

        accumulated_html = ""
        failed = False
        live_evidence: list = []
        live_ruling = None
        with status_placeholder.status(
            "Gathering evidence and briefing the advocates (this can take up to a minute)...",
            expanded=True,
        ) as status:
            try:
                for event in stream_events(
                    st.session_state.get("payload") or {}, demo_mode=st.session_state.demo_mode
                ):
                    kind = event.get("type")
                    if kind == "evidence_data":
                        live_evidence.append(event["data"])
                    elif kind == "ruling_data":
                        live_ruling = event["data"]
                    elif kind == "brief_data":
                        pass  # advocate positions already arrive as log lines
                    elif "agent" in event:
                        st.session_state.agent_log.append(event)
                        accumulated_html += _message_html(event)
                        courtroom_placeholder.markdown(accumulated_html, unsafe_allow_html=True)
                if live_ruling is None:
                    raise BackendError("The stream ended without a ruling.")
                st.session_state.evidence = live_evidence
                st.session_state.ruling = live_ruling
                status.update(label="Resolution complete", state="complete")
            except BackendError as e:
                failed = True
                st.session_state.error = str(e)
                st.session_state.evidence = live_evidence
                status.update(label="Resolution failed", state="error")
        st.session_state.resolving = False
        if not failed:
            st.session_state.error = None
        st.rerun()

    if st.session_state.error:
        st.error(
            f"{st.session_state.error} Check that the backend is running, "
            "or switch on demo mode in the sidebar."
        )

    # --- Step 3: Courtroom log ---
    if st.session_state.agent_log:
        render_courtroom_log(st.session_state.agent_log)

    # --- Step 4: Evidence cards ---
    if st.session_state.evidence:
        st.divider()
        st.subheader("Evidence")
        col_e1, col_e2 = st.columns(2)
        for i, ev in enumerate(st.session_state.evidence):
            target = col_e1 if i % 2 == 0 else col_e2
            with target:
                render_evidence_card(ev)

    # --- Step 5: Ruling cards ---
    if st.session_state.ruling:
        st.divider()
        st.subheader("Ruling")
        col_r, col_d = st.columns(2)
        with col_r:
            render_ruling_card(st.session_state.ruling, audience="rider")
        with col_d:
            render_ruling_card(st.session_state.ruling, audience="driver")


if __name__ == "__main__":
    main()
