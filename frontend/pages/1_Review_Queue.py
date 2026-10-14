"""Human review queue page: escalated cases, approve / override."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from components.ruling_cards import OUTCOME_LABELS, claim_checks_html, render_evidence_card
from review_queue import list_queue, seed_samples, submit_decision
from state import DEFAULT_DEMO_MODE
from theme import section_head

DECISION_OUTCOMES = ["charge_reversed", "charge_upheld", "refund", "compensation", "no_action"]
TYPE_LABELS = {"no_show_charge": "No-Show Charge", "route_deviation": "Route Deviation"}


def _decision_form(item: dict, source: str) -> None:
    key = item["dispute_id"]
    suggested = item.get("suggested_outcome")
    with st.form(f"decision_{key}"):
        st.markdown("**Reviewer decision**")
        if suggested:
            st.caption(
                f"AI recommendation: {OUTCOME_LABELS.get(suggested, suggested)} "
                f"(S${item.get('suggested_amount_sgd') or 0:.2f})"
            )
        else:
            st.caption("No AI recommendation: the Judge escalated instead of deciding.")
        c1, c2 = st.columns(2)
        outcome = c1.selectbox(
            "Final outcome",
            DECISION_OUTCOMES,
            index=DECISION_OUTCOMES.index(suggested) if suggested in DECISION_OUTCOMES else 0,
            format_func=lambda o: OUTCOME_LABELS.get(o, o),
            key=f"outcome_{key}",
        )
        amount = c2.number_input(
            "Amount (SGD)", min_value=0.0, step=0.5,
            value=float(item.get("suggested_amount_sgd") or 0.0), key=f"amount_{key}",
        )
        note = st.text_area("Reviewer note (kept with the case)", key=f"note_{key}")
        b1, b2, _ = st.columns([1.3, 1.3, 2])
        approve = b1.form_submit_button(
            "✅ Approve suggestion", disabled=not suggested, type="primary"
        )
        override = b2.form_submit_button("✏️ Submit my decision" if not suggested else "✏️ Override")
    if approve or override:
        if approve:
            decision, outcome, amount = "approve", suggested, float(item.get("suggested_amount_sgd") or 0.0)
        else:
            decision = "override"
        try:
            submit_decision(item, source, decision, outcome, amount, note.strip())
        except RuntimeError as e:
            st.error(str(e))
            return
        st.rerun()


def _render_item(item: dict, source: str) -> None:
    ruling = item.get("ruling") or {}
    decision = item.get("decision")
    badge = "🔴 High priority" if item.get("priority") == "high" else "🟡 Normal"
    status = "Resolved" if item["status"] == "resolved" else "Pending"
    title = (
        f"{badge} · {item['dispute_id']} · "
        f"{TYPE_LABELS.get(item.get('dispute_type'), item.get('dispute_type') or '—')} · {status}"
    )
    with st.expander(title, expanded=item["status"] == "pending" and item.get("priority") == "high"):
        st.markdown(f"**Filed by:** {item.get('filed_by') or '—'}")
        if item.get("description"):
            st.markdown(f"> {item['description']}")
        st.warning(f"Why escalated: {item.get('escalation_reason') or ruling.get('escalation_reason') or '—'}")
        clauses = ruling.get("clauses_cited") or []
        st.markdown("**Clauses cited:** " + (" ".join(f"`{c}`" for c in clauses) if clauses else "—"))
        st.caption(f"AI confidence: {(ruling.get('confidence') or 0):.0%}")
        claims = claim_checks_html(ruling, said="Filer said")
        if claims:
            st.markdown(claims, unsafe_allow_html=True)

        if item.get("evidence"):
            with st.expander("Evidence"):
                for ev in item["evidence"]:
                    render_evidence_card(ev)

        if item["status"] == "resolved" and decision:
            label = OUTCOME_LABELS.get(decision["outcome"], decision["outcome"])
            kind = "Approved AI recommendation" if decision["decision"] == "approve" else "Overridden by reviewer"
            st.success(f"{kind}: {label}, S${decision['amount_sgd']:.2f}")
            if decision.get("note"):
                st.markdown(f"**Note:** {decision['note']}")
        elif item["status"] == "pending":
            _decision_form(item, source)


section_head(
    "Staff only", "Review queue",
    "Cases the AI did not decide: low confidence, missing evidence, or safety. Safety cases are never auto-resolved.",
)

if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = DEFAULT_DEMO_MODE
if st.session_state.demo_mode:
    seed_samples()

items, source = list_queue()
if source == "local":
    st.info(
        "Backend review queue not available yet. Showing escalated cases from this browser session"
        + (" plus sample cases (demo mode)." if st.session_state.demo_mode else ".")
    )

pending = [i for i in items if i["status"] == "pending"]
m1, m2, m3 = st.columns(3)
m1.metric("Pending", len(pending))
m2.metric("High priority", sum(i.get("priority") == "high" for i in pending))
m3.metric("Resolved", sum(i["status"] == "resolved" for i in items))

view = st.radio("Show", ["Pending", "Resolved", "All"], horizontal=True)
shown = [
    i for i in items
    if view == "All" or i["status"] == view.lower()
]
shown.sort(key=lambda i: (i["status"] != "pending", i.get("priority") != "high"))

if not shown:
    st.write("No cases here. Escalated cases from the Dispute page appear in this queue.")
for item in shown:
    _render_item(item, source)
