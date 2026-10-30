"""Diagram Workspace: large viewer with zoom, pan, enhancement and info."""

from __future__ import annotations

import streamlit as st

from modules.document_reader import DocumentKind, LoadedDocument
from ui.components import (
    empty_state,
    key_values,
    nav_button,
    panel,
    section_heading,
    show_image,
)
from ui.features import Status
from ui.state import PageImages, load_page_images, reset_view
from ui.viewer import crop_view


def _page_controls(document: LoadedDocument) -> None:
    with panel("ws-page"):
        section_heading("Page and resolution")
        if document.kind is DocumentKind.PDF:
            if document.page_count > 1:
                st.number_input(
                    "PDF page", min_value=1, max_value=document.page_count, step=1, key="ws_page"
                )
            else:
                st.caption("Single-page PDF.")
            st.slider("Render resolution (DPI)", 75, 300, step=25, key="ws_dpi")
        else:
            st.caption("Image file: one page at its native resolution.")


def _enhancement_controls() -> None:
    with panel("ws-enhance"):
        section_heading(
            "Image enhancement", "Optional. The original image is never changed."
        )
        st.checkbox("Grayscale", key="pp_gray")
        st.checkbox("Contrast enhancement (CLAHE)", key="pp_contrast")
        st.slider(
            "Contrast clip limit", 1.0, 6.0, step=0.5, key="pp_clip",
            disabled=not st.session_state.pp_contrast,
        )
        st.checkbox("Limit longest side", key="pp_resize")
        st.slider(
            "Max dimension (px)", 800, 6000, step=100, key="pp_maxdim",
            disabled=not st.session_state.pp_resize,
        )
        st.checkbox("Adaptive threshold (black and white)", key="pp_threshold")


def _overlay_panel() -> None:
    with panel("ws-overlay"):
        section_heading(
            "AI detection overlays",
            "Reserved for evidence boxes once detection exists.",
            status=Status.PLANNED,
        )
        for name in ("Equipment symbols", "Instrument tags", "Process lines", "Low-confidence items"):
            st.checkbox(name, value=False, disabled=True, key=f"ov_{name}")
        st.caption("No detections exist yet, so nothing can be drawn on the page.")


def _viewer(images: PageImages) -> None:
    with panel("ws-viewer"):
        if images.error:
            st.error(images.error)
        if images.base is None:
            return
        c_view, c_zoom, c_x, c_y, c_reset = st.columns(
            [1.5, 1.6, 1.3, 1.3, 0.9], vertical_alignment="bottom"
        )
        if images.processed is not None:
            c_view.radio("View", ["Original", "Preprocessed"], horizontal=True, key="ws_view")
        else:
            c_view.caption("Original. Turn on an enhancement to compare.")
        zoom = c_zoom.slider("Zoom", 1.0, 8.0, step=0.5, key="ws_zoom")
        c_x.slider("Pan horizontal (%)", 0, 100, key="ws_pan_x", disabled=zoom <= 1.0)
        c_y.slider("Pan vertical (%)", 0, 100, key="ws_pan_y", disabled=zoom <= 1.0)
        c_reset.button("Reset", on_click=reset_view, icon=":material/restart_alt:")

        use_processed = images.processed is not None and st.session_state.ws_view == "Preprocessed"
        source = images.processed if use_processed else images.base
        view = crop_view(source, zoom, st.session_state.ws_pan_x, st.session_state.ws_pan_y)
        width, height = source.size
        show_image(view, caption=f"Source {width} x {height} px, zoom {zoom:.1f}x")


def _info_panel(document: LoadedDocument, images: PageImages) -> None:
    section_heading("Drawing information")
    pairs = [
        ("File", document.filename),
        ("Format", document.file_format.upper()),
        ("Pages", document.page_count),
        ("Active page", images.page_index + 1),
        ("File size", f"{document.size_bytes / 1e6:.2f} MB"),
    ]
    if images.base is not None:
        pairs.append(("Rendered", f"{images.base.width} x {images.base.height} px"))
    key_values(pairs)


def render() -> None:
    """Draw the workspace."""
    document = st.session_state.document
    if document is None:
        empty_state(
            "No drawing to inspect",
            "Upload a PDF or image first. It will open here with zoom, pan and enhancement tools.",
            "workspace",
        )
        nav_button("upload", "Upload a P&ID", where="workspace", primary=True,
                   icon=":material/upload_file:")
        return

    main, side = st.columns([4.2, 1.6], gap="medium")
    with side:
        info_box = panel("ws-info")  # filled after the page is rendered
        _page_controls(document)
        _enhancement_controls()
        _overlay_panel()
    images = load_page_images(include_processed=True)
    with main:
        _viewer(images)
    with info_box:
        _info_panel(document, images)
