"""Control Philosophy: planned loop and logic structures plus a syntax-only grouping."""

from __future__ import annotations

import streamlit as st

from modules.engineering_lists import (
    ALARM_TABLE,
    CONTROL_LOOP_TABLE,
    INTERLOCK_TABLE,
    group_instrument_loops,
)
from ui.components import (
    callout,
    panel,
    schema_table,
    section_heading,
    stretch,
)
from ui.features import Status


def _syntax_loops() -> None:
    groups, unparsed = group_instrument_loops(st.session_state.graph.equipment())
    with panel("cp-syntax"):
        section_heading(
            "Instrument loops by tag name",
            "Groups instruments you entered that share a first letter and loop number.",
            status=Status.EXPERIMENTAL,
        )
        if not groups and not unparsed:
            st.caption("Enter instruments (type Instrument) on the Engineering Lists page to see groups.")
            return
        stretch(
            st.dataframe,
            [
                {
                    "Loop": g.loop_id,
                    "Measured variable": g.measured_variable,
                    "Tags": ", ".join(g.tags),
                    "Count": len(g.tags),
                }
                for g in groups
            ] or {"Loop": [], "Measured variable": [], "Tags": [], "Count": []},
            hide_index=True,
        )
        if unparsed:
            st.caption("Not recognised as instrument tags: " + ", ".join(unparsed))
        st.caption(
            "This is a naming heuristic. Matching numbers do not prove two instruments "
            "share a physical loop. Confirm on the drawing."
        )


def render() -> None:
    """Draw the control philosophy section."""
    callout(
        "Control-loop and control-logic interpretation is not built. The tables below "
        "show the structure future results will use and are empty.",
        Status.PLANNED,
        lead="Not available yet.",
    )
    _syntax_loops()
    st.write("")
    for spec, name in (
        (CONTROL_LOOP_TABLE, "cp-loops"),
        (INTERLOCK_TABLE, "cp-interlocks"),
        (ALARM_TABLE, "cp-alarms"),
    ):
        with panel(name):
            section_heading(spec.title, spec.description, status=Status.PLANNED)
            schema_table(spec)
        st.write("")
