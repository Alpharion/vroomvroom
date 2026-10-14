"""RydeResolve — Dispute Resolution Frontend (Streamlit)

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
from components.courtroom_log import LOG_HEIGHT, chat_html, render_courtroom_log, render_briefs, typing_html
from components.flow import STAGES, render_stepper
from components.friendly import friendly_error, friendly_evidence_line
from components.route_map import load_trip_geo, render_route_map
from components.ruling_cards import (
    claim_checks_html,
    evidence_tiles_html,
    render_evidence_card,
    render_ruling_card,
    verdict_banner_html,
)
from review_queue import record_appeal, record_escalation
from theme import MODES, brand_html, hero_html, inject_theme, section_head

st.set_page_config(
    page_title="RydeResolve — Dispute Resolution",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
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
        # The toggle has its own key: Streamlit deletes a widget's value on any
        # run where the widget isn't drawn (e.g. while on the review queue page),
        # which would silently reset demo_mode to its default.
        st.toggle(
            "Demo mode (simulated data)",
            value=st.session_state.demo_mode,
            key="_demo_mode_toggle",
            on_change=lambda: st.session_state.update(demo_mode=st.session_state._demo_mode_toggle),
        )
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
    section_head(
        "Step 2", "The hearing, live",
        "Each advocate speaks from their own side. The judge speaks last. Policy clauses appear as small tags.",
    )
    stepper = st.empty()
    render_stepper(1, stepper)
    with st.container(height=LOG_HEIGHT, border=True):
        courtroom_placeholder = st.empty()
    status_placeholder = st.empty()

    failed = False
    live_evidence: list = []
    live_briefs: list = []
    live_log: list = []
    live_ruling = None
    pending_raw = None
    typing = ""

    def draw() -> None:
        courtroom_placeholder.markdown(
            chat_html(live_log, trailing=typing, briefs=live_briefs, ruling=live_ruling), unsafe_allow_html=True
        )

    def show(msg: dict) -> None:
        live_log.append(msg)
        draw()

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
                    typing = typing_html("judge", "The advocates are preparing their cases")
                    draw()
                    status.update(
                        label="Evidence gathered. The advocates are preparing their cases "
                        "(this can take up to a minute)..."
                    )
                elif kind == "ruling_data":
                    live_ruling = event["data"]
                    render_stepper(4, stepper)
                    draw()
                elif kind == "brief_data":
                    live_briefs.append(event["data"])
                    both = len(live_briefs) >= 2
                    render_stepper(3 if both else 2, stepper)
                    typing = typing_html("judge", "The judge is deliberating") if both else typing
                    draw()
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
                    if event["agent"] == "judge":
                        typing = ""
                    show(event)
            typing = ""
            draw()
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

    section_head("Step 3", "The ruling")
    st.markdown(verdict_banner_html(ruling), unsafe_allow_html=True)
    st.write("")

    order = ["rider", "driver"] if filer == "rider" else ["driver", "rider"]
    for col, audience, align in zip(st.columns(2), order, ("left", "right")):
        with col:
            render_ruling_card(ruling, audience=audience, highlight=audience == filer, popup_align=align)

    claims = claim_checks_html(ruling)
    if claims:
        st.markdown(claims, unsafe_allow_html=True)

    if not ruling.get("escalated"):
        st.write("")
        if st.session_state.appealed:
            st.info("Sent. A person will look at this case. You can find it in the review queue.")
        else:
            left, right = st.columns([2, 3], vertical_alignment="center")
            if left.button("Ask for a person to review this decision"):
                record_appeal(st.session_state.payload, ruling, st.session_state.evidence)
                st.session_state.appealed = True
                st.rerun()
            right.caption("Safety concerns are always reviewed by a person.")


@st.fragment
def _evidence_tab(technical: bool) -> None:
    """A fragment, so opening an Expand dialog reruns only this tab and not the whole page."""
    tiles = evidence_tiles_html(st.session_state.evidence)
    if tiles:
        st.markdown(tiles, unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    for i, ev in enumerate(st.session_state.evidence):
        with (col_a if i % 2 == 0 else col_b):
            render_evidence_card(ev, technical=technical, index=i)


def _render_how_we_decided() -> None:
    section_head("How we decided", "The evidence behind the ruling")
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
            render_courtroom_log(
                st.session_state.agent_log, technical=technical,
                briefs=st.session_state.briefs, ruling=st.session_state.ruling,
            )
    with tabs[1]:
        if st.session_state.briefs:
            render_briefs(st.session_state.briefs, expanded=True)
        else:
            st.caption("No advocate briefs for this result.")
    with tabs[2]:
        _evidence_tab(technical)
    if geo:
        with tabs[3]:
            render_route_map(geo)


def file_dispute_page() -> None:
    _init_state()
    _developer_tools()
    # One slot for the whole page body: a new run replaces the old content at once,
    # instead of leaving the previous screen faded underneath while the agents stream.
    with st.empty().container():
        _file_dispute_body()


def _file_dispute_body() -> None:
    if st.session_state.demo_mode:
        st.info("Demo mode: everything shown is simulated, not live.")

    if st.session_state.resolving:
        _run_hearing()
        return

    if st.session_state.ruling is None:
        st.markdown(hero_html(), unsafe_allow_html=True)
        section_head("Step 1", "Tell us what happened")
        render_stepper(0)
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
    head, action = st.columns([4, 1], vertical_alignment="center")
    head.markdown(_dispute_summary())
    if action.button("File another dispute"):
        _reset_result()
        st.session_state.payload = None
        st.rerun()
    _render_ruling_section()
    st.divider()
    _render_how_we_decided()


file_page = st.Page(file_dispute_page, title="File a dispute", default=True)
review_page = st.Page("pages/1_Review_Queue.py", title="Review queue (staff)")


def _header() -> None:
    with st.container(key="vp_header"):
        brand, link_a, link_b, theme = st.columns([2.6, 2, 2.8, 3], vertical_alignment="center")
        brand.markdown(brand_html(), unsafe_allow_html=True)
        link_a.page_link(file_page, label="File a dispute")
        link_b.page_link(review_page, label="Review queue (staff)")
        theme.segmented_control(
            "Theme", MODES, default="Auto", key="theme_mode", label_visibility="collapsed",
            help="Light, dark, or follow your device",
        )


def main() -> None:
    nav = st.navigation([file_page, review_page], position="hidden")
    inject_theme()
    _header()
    nav.run()


if __name__ == "__main__":
    main()
