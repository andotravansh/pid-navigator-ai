"""Export & Reports: CSV for manual lists; other formats are planned."""

from __future__ import annotations

import streamlit as st

from modules.engineering_lists import (
    EQUIPMENT_LIST,
    INSTRUMENT_LIST,
    VALVE_LIST,
    equipment_rows,
    instrument_rows,
    split_records,
    to_csv_bytes,
    valve_rows,
)
from ui.components import callout, feature_card, panel, section_heading, stretch
from ui.features import Status
from ui.state import log_activity

PLANNED_FORMATS = (
    ("Excel workbook", "export", "One sheet per engineering list, ready for review and sign-off."),
    ("PDF report", "file", "A summary report of the drawing, the lists and the open questions."),
    ("AutoCAD DXF", "workspace", "Drawing-compatible output for equipment and line schematics."),
)


def _csv_downloads() -> None:
    parts = split_records(st.session_state.graph.equipment())
    exports = (
        (EQUIPMENT_LIST, equipment_rows(parts["equipment"]), "equipment_list.csv"),
        (VALVE_LIST, valve_rows(parts["valve"]), "valve_list.csv"),
        (INSTRUMENT_LIST, instrument_rows(parts["instrument"]), "instrument_list.csv"),
    )
    with panel("ex-csv"):
        section_heading(
            "CSV download",
            "Lists of items you entered by hand. Blank columns stay blank.",
            status=Status.IMPLEMENTED,
        )
        columns = st.columns(len(exports), gap="medium")
        for column, (spec, rows, filename) in zip(columns, exports):
            with column:
                st.markdown(f"**{spec.title}**")
                st.caption(f"{len(rows)} item(s)")
                clicked = stretch(
                    st.download_button,
                    "Download CSV",
                    data=to_csv_bytes(spec.columns, rows),
                    file_name=filename,
                    mime="text/csv",
                    key=f"dl_{spec.key}",
                    disabled=not rows,
                    icon=":material/download:",
                )
                if clicked:
                    log_activity(f"Downloaded {filename}")
        st.caption("Line List and Control Valve List have no data to export yet.")


def render() -> None:
    """Draw the export section."""
    callout(
        "Only CSV is available, and only for manually entered lists. Excel, PDF and DXF "
        "outputs are not built.",
        Status.EXPERIMENTAL,
        lead="Partial.",
    )
    _csv_downloads()
    st.write("")
    columns = st.columns(len(PLANNED_FORMATS), gap="medium")
    for column, (title, icon, text) in zip(columns, PLANNED_FORMATS):
        with column:
            feature_card(title, text, icon, Status.PLANNED)
            stretch(st.button, "Not available yet", disabled=True, key=f"planned_{title}")
