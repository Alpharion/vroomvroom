"""Ryde Track — Dispute Resolution Frontend (Streamlit)

Run:
    cd frontend
    pip install -r requirements.txt
    streamlit run app.py

Flow: File -> the hearing (live, agents build their cases) -> the ruling
(rider and driver explanations) -> how we decided (log, briefs, evidence, route).
The Review Queue page is for staff.
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
from components.courtroom_log import LOG_HEIGHT, render_courtroom_log, render_briefs, _message_html
from components.flow import STAGES, render_stepper
from components.friendly import friendly_error, friendly_evidence_line, outcome_headline
from components.route_map import load_trip_geo, render_route_map
from components.ruling_cards import render_ruling_card, render_evidence_card
from review_queue import record_appeal, record_escalation

st.set_page_config(
    page_title="Ryde Track — Dispute Resolution",
    page_icon="⚖️",
    layout="wide",
)

_DONE = len(STAGES)  # stepper value meaning every step is finished


def _reset_result() -> None:
    st.session_state.agent_log = []
    st.session_state.evidence = []
    st.session_state.briefs = []
    st.session_state.ruling = None
    st.session_state.error = None
    st.session_state.error_detail = None
    st.session_state.appealed = False


def _init_state() -> None:
    defaults = {
        "demo_mode": DEFAULT_DEMO_MODE,
        "resolving": False,
        "payload": None,
        "show_technical": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if "ruling" not in st.session_state:
        _reset_result()


def _developer_tools() -> None:
    with st.sidebar.expander("Developer tools"):
        st.toggle("Demo mode (simulated data)", key="demo_mode")
        if st.button("Load mock result", disabled=st.session_state.resolving):
            _reset_result()
            st.session_state.agent_log = load_mock_agent_log()
            st.session_state.evidence = load_mock_evidence()
            st.session_state.ruling = load_mock_ruling()
            st.rerun()
        if st.button("Clear", disabled=st.session_state.resolving):
            _reset_result()
            st.rerun()


def _dispute_summary() -> str:
    ticket = (st.session_state.payload or {}).get("dispute_ticket", {})
    kind = {"no_show_charge": "No-show fee", "route_deviation": "Longer route"}.get(
        ticket.get("dispute_type"), "Dispute"
    )
    return f"**{kind}** · filed by the **{ticket.get('filed_by', 'rider')}** · case `{ticket.get('dispute_id', '—')}`"


def _run_hearing() -> None:
    """Stream the agents live. The courtroom stays on screen so the agents' exchange is visible."""
    st.subheader("The hearing")
    st.caption("Two advocates, one for each side, review the evidence. Then a judge decides.")
    stepper = st.empty()
    render_stepper(1, stepper)
    with st.container(height=LOG_HEIGHT, border=True):
        courtroom_placeholder = st.empty()
    status_placeholder = st.empty()

    accumulated_html = ""
    failed = False
    live_evidence: list = []
    live_briefs: list = []
    live_log: list = []
    live_ruling = None
    pending_raw = None

    def show(msg: dict) -> None:
        nonlocal accumulated_html
        live_log.append(msg)
        accumulated_html += _message_html(msg)
        courtroom_placeholder.markdown(accumulated_html, unsafe_allow_html=True)

    with status_placeholder.status("Checking the evidence...", expanded=False) as status:
        try:
            for event in stream_events(
                st.session_state.get("payload") or {}, demo_mode=st.session_state.demo_mode
            ):
                kind = event.get("type")
                if kind == "evidence_data":
                    data = event["data"]
                    live_evidence.append(data)
                    line = friendly_evidence_line(data.get("tool", ""), data.get("facts", {}), data.get("flags"))
                    show({
                        "agent": "system", "type": "evidence",
                        "content": line or pending_raw or f"{data.get('tool', 'Evidence')} checked.",
                        "raw": pending_raw,
                    })
                    pending_raw = None
                    status.update(
                        label="Evidence gathered. The advocates are preparing their cases "
                        "(this can take up to a minute)..."
                    )
                elif kind == "ruling_data":
                    live_ruling = event["data"]
                    render_stepper(4, stepper)
                elif kind == "brief_data":
                    live_briefs.append(event["data"])
                    both = len(live_briefs) >= 2
                    render_stepper(3 if both else 2, stepper)
                    status.update(
                        label="Both advocates have filed. The judge is deliberating..."
                        if both
                        else f"The {live_briefs[-1]['side']} advocate has filed. Waiting for the other side..."
                    )
                elif "agent" in event:
                    if event["agent"] == "system" and event.get("type") == "evidence":
                        pending_raw = event.get("content")  # shown as a readable line on evidence_data
                        continue
                    if event["agent"] in ("rider_advocate", "driver_advocate"):
                        render_stepper(2, stepper)
                    show(event)
            if live_ruling is None:
                raise BackendError("The stream ended without a ruling.")
            st.session_state.evidence = live_evidence
            st.session_state.briefs = live_briefs
            st.session_state.agent_log = live_log
            st.session_state.ruling = live_ruling
            record_escalation(st.session_state.get("payload"), live_ruling, live_evidence)
            status.update(label="The judge has ruled", state="complete")
        except BackendError as e:
            failed = True
            st.session_state.error = friendly_error(str(e))
            st.session_state.error_detail = str(e)
            st.session_state.evidence = live_evidence
            st.session_state.briefs = live_briefs
            st.session_state.agent_log = live_log
            status.update(label="Something went wrong", state="error")
    st.session_state.resolving = False
    if not failed:
        st.session_state.error = None
    st.rerun()


def _render_ruling_section() -> None:
    ruling = st.session_state.ruling
    ticket = (st.session_state.payload or {}).get("dispute_ticket", {})
    filer = ticket.get("filed_by", "rider")

    st.subheader("The ruling")
    if ruling.get("escalated"):
        st.warning(
            f"**{outcome_headline(ruling)}** Safety concerns, missing evidence and low-confidence "
            f"cases are never decided automatically. Reason: {ruling.get('escalation_reason') or 'low confidence'}. "
            "It is now in the review queue."
        )
    else:
        st.success(f"**{outcome_headline(ruling)}**")

    order = ["rider", "driver"] if filer == "rider" else ["driver", "rider"]
    for col, audience in zip(st.columns(2), order):
        with col:
            render_ruling_card(ruling, audience=audience, highlight=audience == filer)

    if not ruling.get("escalated"):
        if st.session_state.appealed:
            st.info("Sent. A person will look at this case. You can find it in the review queue.")
        elif st.button("Ask for a person to review this decision"):
            record_appeal(st.session_state.payload, ruling, st.session_state.evidence)
            st.session_state.appealed = True
            st.rerun()


def _render_how_we_decided() -> None:
    st.subheader("How we decided")
    technical = st.toggle("Show technical details", key="show_technical")

    tab_names = ["Courtroom", "Advocate briefs", "Evidence"]
    ticket = (st.session_state.payload or {}).get("dispute_ticket", {})
    geo = load_trip_geo(ticket.get("dispute_id") or st.session_state.ruling.get("dispute_id", ""))
    if geo:
        tab_names.append("Route replay")
    tabs = st.tabs(tab_names)

    with tabs[0]:
        st.caption("What the agents said, in order.")
        if st.session_state.agent_log:
            render_courtroom_log(st.session_state.agent_log, technical=technical)
    with tabs[1]:
        if st.session_state.briefs:
            render_briefs(st.session_state.briefs, expanded=True)
        else:
            st.caption("No advocate briefs for this result.")
    with tabs[2]:
        col_a, col_b = st.columns(2)
        for i, ev in enumerate(st.session_state.evidence):
            with (col_a if i % 2 == 0 else col_b):
                render_evidence_card(ev, technical=technical)
    if geo:
        with tabs[3]:
            render_route_map(geo)


def file_dispute_page() -> None:
    st.title("Ryde Track")
    st.caption("Fair, fast dispute resolution for riders and drivers")

    _init_state()
    _developer_tools()
    if st.session_state.demo_mode:
        st.info("Demo mode: everything shown is simulated, not live.")

    if st.session_state.resolving:
        _run_hearing()
        return

    if st.session_state.ruling is None:
        render_stepper(0)
        st.markdown(
            "**How it works:** you tell us what happened. Two AI advocates, one for each side, "
            "gather the evidence and argue their case. A judge then decides, usually within a minute. "
            "Anything involving safety goes to a person."
        )
        if st.session_state.error:
            st.error(st.session_state.error)
            with st.expander("Technical detail"):
                st.code(st.session_state.error_detail or "")
                st.caption("Is the backend running? You can also switch on demo mode under Developer tools.")
            if st.session_state.payload and st.button("Try again"):
                _reset_result()
                st.session_state.resolving = True
                st.rerun()
        payload = render_dispute_form()
        if payload is not None:
            _reset_result()
            st.session_state.payload = payload
            st.session_state.resolving = True
            st.rerun()
        return

    # --- Result ---
    render_stepper(_DONE)
    head, action = st.columns([4, 1])
    head.markdown(_dispute_summary())
    if action.button("File another dispute"):
        _reset_result()
        st.session_state.payload = None
        st.rerun()
    _render_ruling_section()
    st.divider()
    _render_how_we_decided()


review_page = st.Page("pages/1_Review_Queue.py", title="Review queue (staff)", icon="🧑‍⚖️")
file_page = st.Page(file_dispute_page, title="File a dispute", icon="⚖️", default=True)

if __name__ == "__main__":
    st.navigation([file_page, review_page]).run()
