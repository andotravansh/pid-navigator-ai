"""Upload P&ID: validation, current-drawing status and removal."""

from __future__ import annotations

import streamlit as st

from modules.document_reader import (
    MAX_FILE_BYTES,
    MAX_PDF_PAGES,
    SUPPORTED_EXTENSIONS,
    DocumentKind,
)
from ui.components import (
    callout,
    key_values,
    nav_button,
    panel,
    section_heading,
    stretch,
)
from ui.features import Status
from ui.state import handle_upload, remove_document


def render() -> None:
    """Draw the upload section."""
    left, right = st.columns([2, 1.2], gap="large")

    with left:
        with panel("upload-drop"):
            section_heading("Choose a file", "PDF, PNG, JPG, JPEG or WebP.")
            uploaded = st.file_uploader(
                "Upload a P&ID",
                type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
                key=f"uploader_{st.session_state.uploader_nonce}",
                label_visibility="collapsed",
            )
            handle_upload(uploaded)
            if st.session_state.load_error:
                st.error(st.session_state.load_error)

        st.write("")
        callout(
            "Loading a different drawing clears the manual equipment and connections "
            "of the previous one.",
            Status.EXPERIMENTAL,
            lead="Heads up.",
        )
        callout(
            "Drawings are held in memory for this session and are not saved to disk. "
            "Nothing is sent to Google unless you configure a key and opt in on the "
            "AI Assistant page.",
            Status.IMPLEMENTED,
            lead="Privacy.",
        )

    with right:
        document = st.session_state.document
        with panel("upload-status"):
            section_heading("Current drawing")
            if document is None:
                st.caption("No drawing loaded.")
            else:
                kind = "PDF" if document.kind is DocumentKind.PDF else "Image"
                key_values(
                    [
                        ("File", document.filename),
                        ("Type", f"{kind} ({document.file_format.upper()})"),
                        ("Pages", document.page_count),
                        ("Size", f"{document.size_bytes / 1e6:.2f} MB"),
                    ]
                )
                st.write("")
                nav_button("workspace", "Open in workspace", where="upload", primary=True,
                           icon=":material/architecture:")
                stretch(
                    st.button,
                    "Remove drawing from session",
                    key="remove_drawing",
                    on_click=remove_document,
                    icon=":material/delete:",
                )
        st.write("")
        with panel("upload-limits"):
            section_heading("Limits")
            key_values(
                [
                    ("Maximum file size", f"{MAX_FILE_BYTES // (1024 * 1024)} MB"),
                    ("Maximum PDF pages", MAX_PDF_PAGES),
                    ("Checks", "Type, content, corruption"),
                ]
            )
