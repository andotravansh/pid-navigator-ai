"""Dashboard: honest session overview and quick navigation."""

from __future__ import annotations

import streamlit as st

from modules.engineering_lists import split_records
from modules.document_reader import DocumentKind
from ui.components import (
    activity_list,
    badge_html,
    callout,
    empty_state,
    esc,
    feature_card,
    html_block,
    key_values,
    metric_card,
    nav_button,
    panel,
    section_heading,
    stretch,
)
from ui.features import FEATURES, Status, count_by_status

QUICK_LINKS = (
    ("workspace", "Diagram Workspace", "workspace", "Inspect, zoom and enhance the drawing.", Status.IMPLEMENTED),
    ("lists", "Engineering Lists", "lists", "Enter equipment, valves and instruments by hand.", Status.IMPLEMENTED),
    ("workflow", "Process Workflow", "route", "Trace paths and upstream or downstream items.", Status.IMPLEMENTED),
    ("assistant", "AI Assistant", "ai", "Ask questions grounded in the data you entered.", Status.EXPERIMENTAL),
    ("safety", "Safety Explorer", "safety", "Explore hypothetical deviations for education.", Status.IMPLEMENTED),
    ("export", "Export & Reports", "export", "Download CSV lists. Other formats are planned.", Status.EXPERIMENTAL),
)


def _hero() -> None:
    text, actions = st.columns([3, 1.1], vertical_alignment="center", gap="large")
    with text:
        html_block(
            """
<div class="pn-hero">
<div class="pn-hero-title">Welcome to P&amp;ID Navigator</div>
<p>Study piping and instrumentation diagrams in one workspace. This release can open and enhance drawings and hold a process model that you enter by hand. Automatic recognition is under development and is not available yet.</p>
</div>
"""
        )
    with actions:
        nav_button("upload", "Upload a P&ID", where="hero", primary=True, icon=":material/upload_file:")
        nav_button("workspace", "Open workspace", where="hero", icon=":material/architecture:")


def _metrics() -> None:
    document = st.session_state.document
    graph = st.session_state.graph
    parts = split_records(graph.equipment())
    manual_links = len(graph.connections())
    cards = st.columns(4, gap="medium")
    with cards[0]:
        metric_card(
            "Drawings",
            1 if document else 0,
            document.filename if document else "No drawing loaded",
            "file",
        )
    with cards[1]:
        n = len(parts["equipment"])
        metric_card("Equipment", n, "Entered manually" if n else "Nothing entered yet", "box")
    with cards[2]:
        metric_card(
            "Lines",
            0,
            f"Extraction not implemented. Manual connections: {manual_links}.",
            "route",
        )
    with cards[3]:
        n = len(parts["valve"])
        metric_card("Valves", n, "Entered manually" if n else "Nothing entered yet", "valve")


def _drawing_panel() -> None:
    document = st.session_state.document
    with panel("dash-drawing"):
        section_heading("Current drawing")
        if document is None:
            empty_state(
                "No drawing loaded",
                "Upload a PDF or image to inspect it. Files stay in memory for this session only.",
                "upload",
            )
            return
        kind = "PDF" if document.kind is DocumentKind.PDF else "Image"
        key_values(
            [
                ("File", document.filename),
                ("Type", f"{kind} ({document.file_format.upper()})"),
                ("Pages", document.page_count),
                ("Size", f"{document.size_bytes / 1e6:.2f} MB"),
                ("Storage", "Session memory only"),
            ]
        )


def _quick_links() -> None:
    section_heading("Quick navigation")
    for row_start in range(0, len(QUICK_LINKS), 3):
        columns = st.columns(3, gap="medium")
        for column, (key, title, icon, text, status) in zip(
            columns, QUICK_LINKS[row_start:row_start + 3]
        ):
            with column:
                feature_card(title, text, icon, status, link=True)
                nav_button(key, "Open", where="quick")


def _activity_panel() -> None:
    entries = st.session_state.activity
    with panel("dash-activity"):
        section_heading("Recent activity", "Events from this session only.")
        if not entries:
            empty_state("No activity yet", "Uploads, manual entries and analyses appear here.")
        else:
            activity_list(list(reversed(entries))[:8])


def _status_panel() -> None:
    counts = count_by_status()
    with panel("dash-status"):
        section_heading("Feature status")
        html_block(
            "<div style='display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.7rem'>"
            + "".join(
                f"{badge_html(s, f'{counts[s]} {s.value}')}"
                for s in (Status.IMPLEMENTED, Status.EXPERIMENTAL, Status.PLANNED)
            )
            + "</div>"
        )
        with st.expander("See every feature"):
            stretch(
                st.dataframe,
                [
                    {"Feature": f.name, "Section": f.section, "Status": f.status.value.title()}
                    for f in FEATURES
                ],
                hide_index=True,
            )


def render() -> None:
    """Draw the dashboard."""
    _hero()
    st.write("")
    _metrics()
    st.write("")
    left, right = st.columns([2.2, 1], gap="large")
    with left:
        _drawing_panel()
        st.write("")
        _quick_links()
    with right:
        _activity_panel()
        st.write("")
        _status_panel()
    callout(
        "Counts reflect only what you uploaded or typed in this session. "
        "No equipment, line or valve has been detected automatically.",
        Status.IMPLEMENTED,
        lead="About these numbers.",
    )
