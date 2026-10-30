"""Diagram Analysis: planned recognition features and the placeholder extractor."""

from __future__ import annotations

import streamlit as st

from modules.engineering_lists import DETECTION_TABLE
from modules.pid_parser import ExtractionStatus, extract_from_image
from ui.components import (
    callout,
    empty_state,
    feature_card,
    nav_button,
    panel,
    schema_table,
    section_heading,
)
from ui.features import Status
from ui.state import load_page_images, log_activity

CAPABILITIES = (
    ("OCR and tag recognition", "scan", "Read equipment tags, instrument tags and line numbers, with a box and confidence for each."),
    ("Symbol detection", "valve", "Find pumps, vessels, exchangers, columns and valves by their drawing symbols."),
    ("Component counting", "calc", "Count detected components by type and page, linked back to the evidence."),
    ("Line tracing", "route", "Follow process lines between symbols and propose connections for review."),
)


def _run_extraction_panel() -> None:
    images = load_page_images()
    with panel("an-run"):
        section_heading("Extraction interface", "The hook where future detectors will plug in.")
        if images.base is None:
            empty_state(
                "No drawing loaded",
                "Upload a drawing to try the extraction interface.",
                "upload",
            )
            nav_button("upload", "Upload a P&ID", where="analysis", icon=":material/upload_file:")
        else:
            if st.button("Run automatic extraction", icon=":material/play_arrow:"):
                st.session_state.extraction = extract_from_image(images.base, images.page_index)
                log_activity("Ran extraction (not implemented, no detections)")
        result = st.session_state.extraction
        if result is not None:
            if result.status is ExtractionStatus.NOT_IMPLEMENTED:
                st.info(result.message)
            for warning in result.warnings:
                st.caption(warning)


def render() -> None:
    """Draw the analysis section."""
    callout(
        "OCR, symbol detection and component counting are not built. No detections "
        "are made from your drawing, and nothing below is a result.",
        Status.PLANNED,
        lead="Not available yet.",
    )
    columns = st.columns(2, gap="medium")
    for index, (title, icon, text) in enumerate(CAPABILITIES):
        with columns[index % 2]:
            feature_card(title, text, icon, Status.PLANNED)
            st.write("")

    _run_extraction_panel()
    st.write("")
    with panel("an-detect"):
        section_heading("Detections", "Every detection will carry evidence and a confidence.",
                        status=Status.PLANNED)
        schema_table(DETECTION_TABLE)
        st.caption("Empty: no detector exists yet.")
