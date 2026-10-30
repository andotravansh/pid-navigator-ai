"""Safety Explorer: educational deviation analysis on verified, entered data."""

from __future__ import annotations

import streamlit as st

from modules.safety_analyzer import DEVIATIONS, Deviation, analyze_deviation
from ui.components import (
    callout,
    empty_state,
    enum_label,
    panel,
    section_heading,
    stretch,
)
from ui.features import Status


def render() -> None:
    """Draw the safety explorer."""
    graph = st.session_state.graph
    callout(
        "Educational only. This is not a HAZOP, LOPA or safety assessment. It uses just "
        "the verified data you entered, and a missing safeguard here is not proof that none exists.",
        Status.IMPLEMENTED,
        lead="Read before use.",
    )
    tags = [r.tag for r in graph.equipment()]
    if not tags:
        empty_state(
            "No equipment to analyse",
            "Add equipment on the Engineering Lists page first.",
            "safety",
        )
        return

    with panel("sf-pick"):
        col_a, col_b = st.columns(2)
        tag = col_a.selectbox("Equipment", tags, key="safety_tag")
        deviation = col_b.selectbox(
            "Hypothetical deviation", list(Deviation), format_func=lambda d: DEVIATIONS[d].label
        )
    analysis = analyze_deviation(graph, tag, deviation)

    st.write("")
    left, right = st.columns(2, gap="large")
    with left:
        with panel("sf-hazards"):
            section_heading("Potential hazards", "Generic statements, not derived from your drawing.")
            for item in analysis.potential_hazards:
                st.markdown(f"- {item}")
        st.write("")
        with panel("sf-scope"):
            section_heading("Affected scope", "Confirmed connections with a known direction.")
            st.write("Upstream:", ", ".join(analysis.upstream) or "none")
            st.write("Downstream:", ", ".join(analysis.downstream) or "none")
    with right:
        with panel("sf-guards"):
            section_heading("Safeguards found in verified data")
            if analysis.safeguards:
                stretch(
                    st.dataframe,
                    [
                        {
                            "Tag": s.tag,
                            "Type": enum_label(s.equipment_type),
                            "Relation": s.relation,
                            "Why listed": s.reason,
                        }
                        for s in analysis.safeguards
                    ],
                    hide_index=True,
                )
            else:
                st.write("None found in the entered data.")
        st.write("")
        with panel("sf-gaps"):
            section_heading("Missing information")
            for item in analysis.missing_information:
                st.markdown(f"- {item}")
            section_heading("Assumptions requiring engineering review")
            for item in analysis.assumptions:
                st.markdown(f"- {item}")
    st.caption(analysis.notice)
