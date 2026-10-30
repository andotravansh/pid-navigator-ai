"""Quantity Estimation: planned take-off, plus counts of what was typed in."""

from __future__ import annotations

import streamlit as st

from modules.engineering_lists import QUANTITY_TABLE, count_by_type
from ui.components import (
    callout,
    feature_card,
    panel,
    schema_table,
    section_heading,
    stretch,
)
from ui.features import Status


def render() -> None:
    """Draw the quantity estimation section."""
    callout(
        "Component counting and material estimation are not built. Nothing here is "
        "a quantity take-off.",
        Status.PLANNED,
        lead="Not available yet.",
    )
    cards = st.columns(2, gap="medium")
    with cards[0]:
        feature_card(
            "Component quantities", "Counts of valves, instruments and equipment by type and size.",
            "calc", Status.PLANNED,
        )
    with cards[1]:
        feature_card(
            "Material estimation", "Pipe lengths, fittings and supports estimated from line data.",
            "box", Status.PLANNED,
        )
    st.write("")
    with panel("qty-bom"):
        section_heading("Bill of quantities", "Target structure for the future estimate.",
                        status=Status.PLANNED)
        schema_table(QUANTITY_TABLE)
        st.caption("Empty: no quantities have been calculated.")
    st.write("")
    with panel("qty-manual"):
        counts = count_by_type(st.session_state.graph.equipment())
        section_heading(
            "Items you entered",
            "A tally of manual entries by type. It is not a take-off and ignores anything not typed in.",
        )
        if counts:
            stretch(
                st.dataframe,
                [{"Type": k, "Entered": v} for k, v in counts.items()],
                hide_index=True,
            )
        else:
            st.caption("No items entered yet.")
