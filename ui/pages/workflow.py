"""Process Workflow: manual connections, tracing and the NetworkX graph view."""

from __future__ import annotations

import streamlit as st
from pydantic import ValidationError

from modules.pid_parser import (
    CandidateConnection,
    ConnectionStatus,
    Evidence,
    EvidenceSource,
)
from modules.process_graph import CONFIRMED_ONLY, GraphError, ProcessGraph
from ui.components import (
    callout,
    empty_state,
    enum_label,
    error_text,
    panel,
    section_heading,
    stretch,
)
from ui.features import Status
from ui.state import log_activity

_DOT_STYLE = (
    'bgcolor="transparent"; '
    'node [color="#22d3ee", fontcolor="#e6edf7", fontname="Segoe UI"]; '
    'edge [color="#7d8fb3", fontcolor="#93a4bf", fontname="Segoe UI"];'
)


def themed_dot(dot: str) -> str:
    """Add dark-theme colours to the DOT text produced by the graph."""
    return dot.replace("digraph PID {", "digraph PID {\n  " + _DOT_STYLE, 1)


def _add_connection(graph: ProcessGraph, tags: list[str]) -> None:
    with panel("wf-add"):
        section_heading("Add a connection", "Mark it confirmed only after checking the drawing.")
        with st.form("add_connection", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            source = col_a.selectbox("From", tags)
            target = col_b.selectbox("To", tags, index=1)
            direction_known = st.checkbox("Flow direction is known (From to To)", value=True)
            status = st.selectbox("Status", list(ConnectionStatus), format_func=enum_label)
            line_label = st.text_input("Line label or service (optional)")
            submitted = st.form_submit_button("Add connection")
        if not submitted:
            return
        try:
            graph.add_connection(
                CandidateConnection(
                    source_tag=source,
                    target_tag=target,
                    direction_known=direction_known,
                    status=status,
                    line_label=line_label,
                    evidence=[Evidence(source=EvidenceSource.USER_ENTRY, note="Entered by the user.")],
                )
            )
        except (ValidationError, GraphError) as exc:
            st.error(f"Could not add the connection: {error_text(exc)}")
            return
        log_activity(f"Connected {source} to {target} ({enum_label(status)})")
        st.success(f"Added {source} to {target}.")


def _connection_table(graph: ProcessGraph) -> None:
    connections = graph.connections()
    with panel("wf-list"):
        section_heading("Connections")
        if not connections:
            empty_state("No connections", "Add one on the left to build the process model.", "route")
            return
        stretch(
            st.dataframe,
            [
                {
                    "From": c.source_tag,
                    "To": c.target_tag,
                    "Direction known": c.direction_known,
                    "Status": enum_label(c.status),
                    "Line": c.line_label,
                }
                for c in connections
            ],
            hide_index=True,
        )
        pairs = [f"{c.source_tag} | {c.target_tag}" for c in connections]
        chosen = st.selectbox("Select a connection to change", pairs)
        new_status = st.selectbox("New status", list(ConnectionStatus), format_func=enum_label)
        a, b = (part.strip() for part in chosen.split("|"))
        col_u, col_r = st.columns(2)
        if col_u.button("Update status", icon=":material/sync_alt:"):
            graph.set_connection_status(a, b, new_status)
            log_activity(f"{a} to {b} marked {enum_label(new_status)}")
            st.rerun()
        if col_r.button("Remove connection", icon=":material/delete:"):
            graph.remove_connection(a, b)
            log_activity(f"Removed connection {a} to {b}")
            st.rerun()


def _graph_view(graph: ProcessGraph) -> None:
    if not graph.connections():
        return
    with panel("wf-graph"):
        section_heading("Process graph")
        st.graphviz_chart(themed_dot(graph.to_dot()))
        st.caption(
            "Solid is confirmed, dashed is proposed, dotted is uncertain. "
            "No arrow means the direction is unknown."
        )


def _trace(graph: ProcessGraph, tags: list[str]) -> None:
    with panel("wf-trace"):
        section_heading("Trace and analyse")
        statuses = st.multiselect(
            "Connection statuses to include",
            list(ConnectionStatus),
            default=list(CONFIRMED_ONLY),
            format_func=enum_label,
        )
        directed = st.checkbox("Respect flow direction (known-direction connections only)", True)
        if not statuses:
            st.info("Select at least one status.")
            return
        col_from, col_to = st.columns(2)
        path_from = col_from.selectbox("Path from", tags, key="path_from")
        path_to = col_to.selectbox("Path to", tags, index=1, key="path_to")
        paths = graph.find_paths(path_from, path_to, statuses, directed)
        if paths:
            for path in paths:
                st.write(" -> ".join(path))
        else:
            st.info("No path in the selected connections. This reflects the entered data only.")
        focus = st.selectbox("Upstream and downstream of", tags, key="focus_tag")
        st.write("Upstream:", ", ".join(graph.upstream(focus, statuses)) or "none")
        st.write("Downstream:", ", ".join(graph.downstream(focus, statuses)) or "none")
        groups = graph.connected_components(statuses)
        st.write("Connected groups:", "; ".join(", ".join(g) for g in groups) or "none")


def render() -> None:
    """Draw the workflow section."""
    graph: ProcessGraph = st.session_state.graph
    callout(
        "Connections are not detected automatically. Only items you entered appear here, "
        "and an unverified graph is not a record of the plant.",
        Status.EXPERIMENTAL,
        lead="Manual model.",
    )
    tags = [r.tag for r in graph.equipment()]
    if len(tags) < 2:
        empty_state(
            "Add at least two items",
            "Enter equipment on the Engineering Lists page, then connect it here.",
            "lists",
        )
        return
    left, right = st.columns([1, 1.4], gap="large")
    with left:
        _add_connection(graph, tags)
    with right:
        _connection_table(graph)
    st.write("")
    _graph_view(graph)
    st.write("")
    _trace(graph, tags)
