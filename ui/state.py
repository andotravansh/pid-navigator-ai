"""Session state, upload handling and page rendering for the UI.

Drawings live only in ``st.session_state`` (memory). Nothing is written
to disk, and the activity log stores short event texts, never drawing data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import streamlit as st
from PIL import Image

from modules.document_reader import (
    DEFAULT_DPI,
    DocumentError,
    LoadedDocument,
    get_page_image,
    load_document,
)
from modules.image_processor import PreprocessOptions, preprocess
from modules.process_graph import ProcessGraph

MAX_ACTIVITY = 50

# Widget keys whose values must survive navigation between sections.
WIDGET_DEFAULTS: dict[str, Any] = {
    "ws_page": 1,
    "ws_dpi": DEFAULT_DPI,
    "ws_view": "Original",
    "ws_zoom": 1.0,
    "ws_pan_x": 50,
    "ws_pan_y": 50,
    "pp_gray": False,
    "pp_contrast": False,
    "pp_clip": 2.0,
    "pp_resize": False,
    "pp_maxdim": 3000,
    "pp_threshold": False,
}


def init_state() -> None:
    """Create defaults and keep widget values alive across sections."""
    state = st.session_state
    state.setdefault("graph", ProcessGraph())
    state.setdefault("document", None)
    state.setdefault("file_hash", None)
    state.setdefault("load_error", None)
    state.setdefault("extraction", None)
    state.setdefault("ai_response", None)
    state.setdefault("activity", [])
    state.setdefault("uploader_nonce", 0)
    for key, value in WIDGET_DEFAULTS.items():
        state.setdefault(key, value)
        # Re-assigning stops Streamlit discarding a widget's value while
        # its section is not on screen.
        state[key] = state[key]


def log_activity(message: str) -> None:
    """Append a short event to the in-memory activity list."""
    entries: list[tuple[str, str]] = st.session_state.activity
    entries.append((datetime.now().strftime("%H:%M:%S"), message))
    del entries[:-MAX_ACTIVITY]


def reset_view() -> None:
    """Return zoom and pan to the full drawing."""
    st.session_state.ws_zoom = 1.0
    st.session_state.ws_pan_x = 50
    st.session_state.ws_pan_y = 50


def reset_document() -> None:
    """Drop the drawing, the manual model and every derived result."""
    state = st.session_state
    state.document = None
    state.file_hash = None
    state.load_error = None
    state.graph = ProcessGraph()
    state.extraction = None
    state.ai_response = None
    state.ws_page = 1
    state.ws_view = "Original"
    reset_view()


def remove_document() -> None:
    """Remove the drawing and clear the uploader widget."""
    name = st.session_state.document.filename if st.session_state.document else "drawing"
    reset_document()
    st.session_state.uploader_nonce += 1
    log_activity(f"Removed {name} and cleared the manual model")


def handle_upload(uploaded: Any) -> None:
    """Validate a new upload and keep it in memory only."""
    state = st.session_state
    if uploaded is None:
        if state.document is None and state.load_error:
            state.load_error = None
            state.file_hash = None
        return
    data = uploaded.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    if digest == state.file_hash:
        return
    had_model = state.document is not None or len(state.graph) > 0
    reset_document()
    state.file_hash = digest
    result = load_document(uploaded.name, data)
    if result.ok:
        state.document = result.document
        suffix = " (previous manual model cleared)" if had_model else ""
        log_activity(f"Loaded {uploaded.name}{suffix}")
    else:
        state.load_error = result.error
        log_activity(f"Rejected {uploaded.name}: {result.error}")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Rendering page", max_entries=3, ttl=3600)
def cached_page_image(
    _document: LoadedDocument, digest: str, page_index: int, dpi: int
) -> Image.Image:
    """Render a page once per (file, page, dpi). Treat the result as read-only."""
    return get_page_image(_document, page_index, dpi)


def preprocess_options() -> PreprocessOptions:
    """Build preprocessing options from the enhancement widgets."""
    s = st.session_state
    return PreprocessOptions(
        grayscale=bool(s.pp_gray),
        enhance_contrast=bool(s.pp_contrast),
        clip_limit=float(s.pp_clip),
        max_dimension=int(s.pp_maxdim) if s.pp_resize else None,
        threshold=bool(s.pp_threshold),
    )


@dataclass(frozen=True)
class PageImages:
    """The rendered page (and optional enhanced copy) or an error."""

    base: Optional[Image.Image] = None
    processed: Optional[Image.Image] = None
    error: Optional[str] = None
    page_index: int = 0
    dpi: int = DEFAULT_DPI


def load_page_images(include_processed: bool = False) -> PageImages:
    """Render the active page; never raises."""
    document: Optional[LoadedDocument] = st.session_state.document
    if document is None:
        return PageImages()
    page_index = min(max(int(st.session_state.ws_page), 1), document.page_count) - 1
    dpi = int(st.session_state.ws_dpi)
    try:
        base = cached_page_image(document, st.session_state.file_hash, page_index, dpi)
    except DocumentError as exc:
        return PageImages(error=str(exc), page_index=page_index, dpi=dpi)
    processed = None
    if include_processed:
        options = preprocess_options()
        if not options.is_noop:
            try:
                processed = preprocess(base, options)
            except Exception as exc:  # OpenCV and NumPy raise several error types.
                return PageImages(
                    base=base,
                    error=f"Enhancement failed ({type(exc).__name__}). Showing the original.",
                    page_index=page_index,
                    dpi=dpi,
                )
    return PageImages(base=base, processed=processed, page_index=page_index, dpi=dpi)
