"""Engineering Lists: schemas for the five take-off lists plus manual entry."""

from __future__ import annotations

from typing import Any, Sequence

import streamlit as st
from pydantic import ValidationError

from modules.engineering_lists import (
    CONTROL_VALVE_LIST,
    EQUIPMENT_LIST,
    INSTRUMENT_LIST,
    LINE_LIST,
    VALVE_LIST,
    TableSpec,
    equipment_rows,
    instrument_rows,
    split_records,
    valve_rows,
)
from modules.pid_parser import (
    EquipmentRecord,
    EquipmentType,
    Evidence,
    EvidenceSource,
    parse_instrument_tag,
)
from modules.process_graph import GraphError, ProcessGraph
from ui.components import (
    callout,
    empty_state,
    enum_label,
    error_text,
    panel,
    schema_table,
    section_heading,
)
from ui.features import Status
from ui.state import log_activity


def _add_form(graph: ProcessGraph) -> None:
    with st.expander("Add an item by hand", expanded=len(graph) == 0):
        with st.form("add_item", clear_on_submit=True):
            tag = st.text_input("Tag", placeholder="P-101A")
            kind = st.selectbox("Type", list(EquipmentType), format_func=enum_label)
            description = st.text_input("Description (optional)")
            submitted = st.form_submit_button("Add item")
        st.caption(
            "Items are sorted into lists by type. Enter control valves and "
            "transmitters as type Instrument if you want them grouped by loop."
        )
    if not submitted:
        return
    try:
        graph.add_equipment(
            EquipmentRecord(
                tag=tag,
                equipment_type=kind,
                description=description,
                verified=True,
                evidence=[Evidence(source=EvidenceSource.USER_ENTRY, note="Entered by the user.")],
            )
        )
    except (ValidationError, GraphError) as exc:
        st.error(f"Could not add the item: {error_text(exc)}")
        return
    clean = tag.strip().upper()
    log_activity(f"Added {clean} ({enum_label(kind)})")
    st.success(f"Added {clean}.")


def _remove_form(graph: ProcessGraph) -> None:
    tags = [r.tag for r in graph.equipment()]
    if not tags:
        return
    with st.expander("Remove an item"):
        chosen = st.selectbox("Item", tags, key="remove_item_tag")
        st.caption("Removing an item also removes its connections.")
        if st.button("Remove item", icon=":material/delete:"):
            graph.remove_equipment(chosen)
            log_activity(f"Removed {chosen}")
            st.rerun()


def _list_tab(
    spec: TableSpec,
    rows: Sequence[dict[str, Any]],
    empty_title: str,
    empty_message: str,
) -> None:
    with panel(f"list-{spec.key}"):
        section_heading(spec.title, spec.description)
        if not rows:
            empty_state(empty_title, empty_message)
            st.write("")
        schema_table(spec, rows)
        if rows:
            st.caption(f"{len(rows)} item(s) entered by hand. Blank columns are not filled automatically.")


def render() -> None:
    """Draw the engineering lists."""
    graph: ProcessGraph = st.session_state.graph
    callout(
        "Nothing is extracted from the drawing yet. Tables show the columns each "
        "list will hold, plus any items you typed in. Blank cells are unknown, not zero.",
        Status.PLANNED,
        lead="Extraction is planned.",
    )
    _add_form(graph)
    _remove_form(graph)
    parts = split_records(graph.equipment())

    line_tab, valve_tab, control_tab, equipment_tab, instrument_tab = st.tabs(
        ["Line List", "Valve List", "Control Valve List", "Equipment List", "Instrument List"]
    )
    with line_tab:
        _list_tab(
            LINE_LIST, [],
            "No lines listed",
            "Line numbers, services, sizes, insulation and specifications will appear here "
            "once line extraction is built. Manual line entry is not available yet.",
        )
    with valve_tab:
        _list_tab(
            VALVE_LIST, valve_rows(parts["valve"]),
            "No valves entered",
            "Add a valve, check valve or relief device above, or wait for automatic detection.",
        )
    with control_tab:
        _list_tab(
            CONTROL_VALVE_LIST, [],
            "No control valves listed",
            "Control valves are not distinguished from other valves yet. They will be "
            "listed with their actuator and controlling loop once detection exists.",
        )
    with equipment_tab:
        _list_tab(
            EQUIPMENT_LIST, equipment_rows(parts["equipment"]),
            "No equipment entered",
            "Add a pump, vessel, exchanger or column above, or wait for automatic detection.",
        )
    with instrument_tab:
        _list_tab(
            INSTRUMENT_LIST, instrument_rows(parts["instrument"]),
            "No instruments entered",
            "Add an instrument tag such as FIC-101 above, or wait for OCR.",
        )
        with st.expander("Instrument tag helper (syntax only)"):
            text = st.text_input("Tag text", placeholder="FIC-101", key="tag_helper")
            if text:
                parsed = parse_instrument_tag(text)
                if parsed is None:
                    st.info("The text does not match a letters-plus-number instrument pattern.")
                else:
                    st.write(
                        f"Letters **{parsed.isa_letters}**, measured variable (first letter) "
                        f"**{parsed.measured_variable or 'unknown'}**, loop "
                        f"**{parsed.loop_number}{parsed.suffix}**."
                    )
                    st.caption("Syntax only: 'TK-101' also parses, although it is a tank.")
