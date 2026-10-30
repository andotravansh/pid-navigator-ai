"""Section definitions and the sidebar navigation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

from ui import registry
from ui.components import esc, html_block, icon_svg, page_header
from ui.features import Status
from ui.pages import (
    analysis,
    assistant,
    control,
    dashboard,
    export,
    lists,
    quantity,
    safety,
    upload,
    workflow,
    workspace,
)

GROUPS = ("Overview", "Drawing", "Engineering", "Intelligence", "Output")


@dataclass(frozen=True)
class Section:
    """One navigable section of the application."""

    key: str
    title: str
    icon: str  # Material Symbols name
    group: str
    render: Callable[[], None]
    status: Status
    subtitle: str
    badge_label: Optional[str] = None
    show_header: bool = True


SECTIONS: tuple[Section, ...] = (
    Section("dashboard", "Dashboard", "dashboard", "Overview", dashboard.render,
            Status.IMPLEMENTED, "Session overview.", show_header=False),
    Section("upload", "Upload P&ID", "upload_file", "Overview", upload.render,
            Status.IMPLEMENTED, "Add a PDF or image. It is checked and kept in memory only."),
    Section("workspace", "Diagram Workspace", "architecture", "Drawing", workspace.render,
            Status.IMPLEMENTED, "Inspect the drawing with zoom, pan and optional image enhancement."),
    Section("analysis", "Diagram Analysis", "document_scanner", "Drawing", analysis.render,
            Status.PLANNED, "Text recognition, symbol detection and component counting."),
    Section("lists", "Engineering Lists", "list_alt", "Engineering", lists.render,
            Status.IMPLEMENTED, "Line, valve, control valve, equipment and instrument lists.",
            badge_label="Manual entry"),
    Section("workflow", "Process Workflow", "account_tree", "Engineering", workflow.render,
            Status.IMPLEMENTED, "Connect items, trace paths and follow flow upstream or downstream.",
            badge_label="Manual entry"),
    Section("control", "Control Philosophy", "tune", "Engineering", control.render,
            Status.PLANNED, "Control loops, interlocks and alarms."),
    Section("quantity", "Quantity Estimation", "calculate", "Engineering", quantity.render,
            Status.PLANNED, "Component counts and material estimates."),
    Section("assistant", "AI Assistant", "auto_awesome", "Intelligence", assistant.render,
            Status.EXPERIMENTAL, "Ask questions answered only from the data you entered."),
    Section("safety", "Safety Explorer", "health_and_safety", "Intelligence", safety.render,
            Status.IMPLEMENTED, "Explore hypothetical process deviations for learning."),
    Section("export", "Export & Reports", "file_download", "Output", export.render,
            Status.EXPERIMENTAL, "Download lists and, later, reports and drawings.",
            badge_label="Partial"),
)


def _page_function(section: Section) -> Callable[[], None]:
    def run() -> None:
        if section.show_header:
            page_header(section.title, section.subtitle, section.group,
                        section.status, section.badge_label)
        section.render()

    run.__name__ = f"page_{section.key}"
    return run


def _label(section: Section) -> str:
    if section.status is Status.PLANNED:
        return f"{section.title} :gray[(planned)]"
    if section.status is Status.EXPERIMENTAL and section.key == "assistant":
        return f"{section.title} :orange[(experimental)]"
    return section.title


def _brand() -> None:
    html_block(
        f"""
<div class="pn-brand"><div class="pn-brand-mark">{icon_svg("brand", 22)}</div>
<div><div class="pn-brand-name">P&amp;ID Navigator</div>
<div class="pn-brand-sub">Engineering workspace</div></div></div>
"""
    )


def _drawing_note() -> None:
    document = st.session_state.get("document")
    if document is None:
        line = "<b>No drawing loaded</b>"
    else:
        line = f"<b>Drawing loaded</b><br>{esc(document.filename)}"
    html_block(
        f'<div class="pn-sidebar-note">{line}<br>Held in memory for this session. '
        "Nothing is saved to disk.</div>"
    )


def build_navigation():
    """Register the pages, draw the sidebar and return the page to run."""
    pages = {}
    for index, section in enumerate(SECTIONS):
        kwargs = {"default": True} if index == 0 else {"url_path": section.key}
        pages[section.key] = st.Page(
            _page_function(section),
            title=section.title,
            icon=f":material/{section.icon}:",
            **kwargs,
        )
    registry.PAGES.clear()
    registry.PAGES.update(pages)
    current = st.navigation(list(pages.values()), position="hidden")

    with st.sidebar:
        _brand()
        for group in GROUPS:
            html_block(f'<div class="pn-nav-group">{esc(group)}</div>')
            for section in SECTIONS:
                if section.group == group:
                    st.page_link(
                        pages[section.key],
                        label=_label(section),
                        icon=f":material/{section.icon}:",
                    )
        _drawing_note()
    return current
