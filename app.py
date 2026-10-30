"""P&ID Navigator: Streamlit entry point.

Run with:  streamlit run app.py
All uploads stay in memory for the session; nothing is saved to disk.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Optional

import streamlit as st
from PIL import Image
from pydantic import ValidationError

from modules.ai_interpreter import (
    DISCLAIMER,
    AIStatus,
    GeminiInterpreter,
    build_context,
    load_config,
)
from modules.document_reader import (
    DEFAULT_DPI,
    MAX_FILE_BYTES,
    SUPPORTED_EXTENSIONS,
    DocumentError,
    DocumentKind,
    LoadedDocument,
    get_page_image,
    load_document,
)
from modules.image_processor import PreprocessOptions, preprocess
from modules.pid_parser import (
    CandidateConnection,
    ConnectionStatus,
    EquipmentRecord,
    EquipmentType,
    Evidence,
    EvidenceSource,
    ExtractionStatus,
    extract_from_image,
    parse_instrument_tag,
)
from modules.process_graph import (
    ALL_STATUSES,
    CONFIRMED_ONLY,
    GraphError,
    ProcessGraph,
)
from modules.safety_analyzer import DEVIATIONS, Deviation, analyze_deviation

st.set_page_config(page_title="P&ID Navigator", page_icon="🛠️", layout="wide")

FEATURES = [
    {"Feature": "Upload and validate PDF / PNG / JPG / WebP", "Status": "Implemented"},
    {"Feature": "PDF page selection and rendering", "Status": "Implemented"},
    {"Feature": "Zoom and pan inspection", "Status": "Implemented"},
    {"Feature": "Optional image preprocessing (OpenCV)", "Status": "Implemented"},
    {"Feature": "Manual equipment and connection entry", "Status": "Implemented"},
    {"Feature": "Process graph: paths, upstream/downstream, components", "Status": "Implemented"},
    {"Feature": "Educational deviation explorer (verified data only)", "Status": "Implemented"},
    {"Feature": "AI Q&A grounded in entered data", "Status": "Optional (needs Gemini key)"},
    {"Feature": "Automatic tag / OCR extraction", "Status": "Planned"},
    {"Feature": "Automatic symbol and equipment detection", "Status": "Planned"},
    {"Feature": "Automatic line tracing and connection detection", "Status": "Planned"},
    {"Feature": "Evidence overlays on the drawing", "Status": "Planned"},
]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def stretch(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a Streamlit widget with full width across Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except Exception:
        return fn(*args, use_container_width=True, **kwargs)


def label(value: Any) -> str:
    """Human-readable label for an enum value."""
    return str(value.value).replace("_", " ").title()


def error_text(exc: Exception) -> str:
    """Short, friendly text for validation or graph errors."""
    if isinstance(exc, ValidationError):
        return "; ".join(str(e["msg"]) for e in exc.errors())
    return str(exc)


def init_state() -> None:
    """Create session-state defaults."""
    defaults = {
        "graph": ProcessGraph(),
        "document": None,
        "file_hash": None,
        "load_error": None,
        "extraction": None,
        "ai_response": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_document_state() -> None:
    """Drop the current drawing, its model, and derived results from memory."""
    st.session_state.document = None
    st.session_state.file_hash = None
    st.session_state.load_error = None
    st.session_state.graph = ProcessGraph()
    st.session_state.extraction = None
    st.session_state.ai_response = None


def handle_upload(uploaded: Any) -> None:
    """Validate a new upload and keep it in memory only."""
    if uploaded is None:
        if st.session_state.file_hash is not None:
            reset_document_state()
        return
    data = uploaded.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    if digest == st.session_state.file_hash:
        return
    reset_document_state()
    st.session_state.file_hash = digest
    result = load_document(uploaded.name, data)
    if result.ok:
        st.session_state.document = result.document
    else:
        st.session_state.load_error = result.error


@st.cache_data(show_spinner="Rendering page", max_entries=3, ttl=3600)
def cached_page_image(
    _document: LoadedDocument, digest: str, page_index: int, dpi: int
) -> Image.Image:
    """Render a page once per (file, page, dpi); the leading underscore skips hashing."""
    return get_page_image(_document, page_index, dpi)


def show_image(image: Image.Image, caption: Optional[str] = None) -> None:
    """Display an image at full column width across Streamlit versions."""
    try:
        st.image(image, caption=caption, width="stretch")
    except Exception:
        st.image(image, caption=caption, use_container_width=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> tuple[Optional[LoadedDocument], int, int, PreprocessOptions]:
    """Render upload and processing controls; return the chosen settings."""
    st.sidebar.title("P&ID Navigator")
    uploaded = st.sidebar.file_uploader(
        "Upload a P&ID",
        type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
        help=f"PDF, PNG, JPG, JPEG or WebP, up to {MAX_FILE_BYTES // (1024 * 1024)} MB.",
    )
    handle_upload(uploaded)

    if st.session_state.load_error:
        st.sidebar.error(st.session_state.load_error)

    document: Optional[LoadedDocument] = st.session_state.document
    page_index, dpi = 0, DEFAULT_DPI
    if document is not None:
        st.sidebar.success(f"Loaded {document.filename} ({document.size_bytes / 1e6:.1f} MB)")
        if document.kind is DocumentKind.PDF:
            if document.page_count > 1:
                page_index = (
                    int(st.sidebar.number_input("PDF page", 1, document.page_count, 1)) - 1
                )
            dpi = int(st.sidebar.slider("Render resolution (DPI)", 75, 300, DEFAULT_DPI, 25))

    with st.sidebar.expander("Image preprocessing (optional)"):
        grayscale = st.checkbox("Grayscale")
        contrast = st.checkbox("Contrast enhancement (CLAHE)")
        clip = st.slider("Contrast clip limit", 1.0, 6.0, 2.0, 0.5, disabled=not contrast)
        resize = st.checkbox("Limit longest side")
        max_dim = st.slider("Max dimension (px)", 800, 6000, 3000, 100, disabled=not resize)
        threshold = st.checkbox("Adaptive threshold (black and white)")
    options = PreprocessOptions(
        grayscale=grayscale,
        enhance_contrast=contrast,
        clip_limit=float(clip),
        max_dimension=int(max_dim) if resize else None,
        threshold=threshold,
    )

    st.sidebar.info(
        "Privacy: drawings are held in memory for this session only and are not "
        "saved to disk. They are sent to Google only if you opt in on the AI tab."
    )
    return document, page_index, dpi, options


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def render_viewer(base: Optional[Image.Image], processed: Optional[Image.Image]) -> None:
    """Diagram viewer with zoom and pan."""
    if base is None:
        st.info("Upload a PDF or image in the sidebar to begin.")
        return

    source = base
    if processed is not None:
        choice = st.radio("Show", ["Original", "Preprocessed"], horizontal=True)
        source = processed if choice == "Preprocessed" else base

    zoom = st.slider("Zoom", 1.0, 8.0, 1.0, 0.5)
    center_x = center_y = 50
    if zoom > 1.0:
        col_x, col_y = st.columns(2)
        center_x = col_x.slider("Pan horizontal (%)", 0, 100, 50)
        center_y = col_y.slider("Pan vertical (%)", 0, 100, 50)

    width, height = source.size
    crop_w, crop_h = width / zoom, height / zoom
    left = min(max(center_x / 100 * width - crop_w / 2, 0), width - crop_w)
    top = min(max(center_y / 100 * height - crop_h / 2, 0), height - crop_h)
    view = source.crop((round(left), round(top), round(left + crop_w), round(top + crop_h)))
    view.thumbnail((2400, 2400))  # keep browser payload reasonable
    show_image(view, caption=f"Source {width} x {height} px | zoom {zoom:.1f}x")


def render_equipment_tab(base: Optional[Image.Image], page_index: int) -> None:
    """Extraction status, manual entry, and tag helper."""
    graph: ProcessGraph = st.session_state.graph
    st.subheader("Equipment and tags")
    st.warning(
        "Automatic extraction is NOT implemented yet. Nothing on this tab was "
        "detected from the image; every entry below is typed in by you."
    )

    if st.button("Run automatic extraction", disabled=base is None):
        st.session_state.extraction = extract_from_image(base, page_index)
    result = st.session_state.extraction
    if result is not None:
        if result.status is ExtractionStatus.NOT_IMPLEMENTED:
            st.info(result.message)
        for warning in result.warnings:
            st.caption(warning)

    st.markdown("#### Add equipment manually")
    with st.form("add_equipment", clear_on_submit=True):
        tag = st.text_input("Tag", placeholder="P-101A")
        etype = st.selectbox("Type", list(EquipmentType), format_func=label)
        description = st.text_input("Description (optional)")
        submitted = st.form_submit_button("Add equipment")
    if submitted:
        try:
            graph.add_equipment(
                EquipmentRecord(
                    tag=tag,
                    equipment_type=etype,
                    description=description,
                    verified=True,
                    evidence=[
                        Evidence(source=EvidenceSource.USER_ENTRY, note="Entered by the user.")
                    ],
                )
            )
            st.success(f"Added {tag.strip().upper()}.")
        except (ValidationError, GraphError) as exc:
            st.error(f"Could not add equipment: {error_text(exc)}")

    records = graph.equipment()
    if records:
        stretch(
            st.dataframe,
            [
                {
                    "Tag": r.tag,
                    "Type": label(r.equipment_type),
                    "Description": r.description,
                    "Verified": r.verified,
                }
                for r in records
            ],
            hide_index=True,
        )
        to_remove = st.selectbox("Remove equipment", [r.tag for r in records])
        if st.button("Remove selected equipment"):
            graph.remove_equipment(to_remove)
            st.rerun()
    else:
        st.caption("No equipment entered yet.")

    with st.expander("Instrument tag helper (syntax only)"):
        text = st.text_input("Tag text", placeholder="FIC-101")
        if text:
            parsed = parse_instrument_tag(text)
            if parsed is None:
                st.info("Text does not match a letters + number instrument pattern.")
            else:
                st.write(
                    f"Letters: **{parsed.isa_letters}** | Measured variable (first "
                    f"letter): **{parsed.measured_variable or 'unknown'}** | "
                    f"Loop: **{parsed.loop_number}{parsed.suffix}**"
                )
                st.caption(
                    "Syntax only: 'TK-101' would also parse, although it is a tank."
                )


def render_flow_tab() -> None:
    """Manual connections, path tracing, and graph display."""
    graph: ProcessGraph = st.session_state.graph
    st.subheader("Process flow")
    st.warning(
        "Connections are NOT detected automatically. Only mark a connection "
        "'confirmed' after you verified it on the drawing."
    )
    tags = [r.tag for r in graph.equipment()]
    if len(tags) < 2:
        st.info("Add at least two equipment items on the Equipment & Tags tab.")
        return

    with st.form("add_connection", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        source = col_a.selectbox("From", tags)
        target = col_b.selectbox("To", tags, index=1)
        direction_known = st.checkbox("Flow direction is known (From -> To)", value=True)
        status = st.selectbox("Status", list(ConnectionStatus), format_func=label)
        line_label = st.text_input("Line label / service (optional)")
        submitted = st.form_submit_button("Add connection")
    if submitted:
        try:
            graph.add_connection(
                CandidateConnection(
                    source_tag=source,
                    target_tag=target,
                    direction_known=direction_known,
                    status=status,
                    line_label=line_label,
                    evidence=[
                        Evidence(source=EvidenceSource.USER_ENTRY, note="Entered by the user.")
                    ],
                )
            )
            st.success(f"Added {source} to {target}.")
        except (ValidationError, GraphError) as exc:
            st.error(f"Could not add connection: {error_text(exc)}")

    connections = graph.connections()
    if connections:
        stretch(
            st.dataframe,
            [
                {
                    "From": c.source_tag,
                    "To": c.target_tag,
                    "Direction known": c.direction_known,
                    "Status": label(c.status),
                    "Line": c.line_label,
                }
                for c in connections
            ],
            hide_index=True,
        )
        pairs = [f"{c.source_tag} | {c.target_tag}" for c in connections]
        chosen = st.selectbox("Select a connection to change", pairs)
        col_s, col_r = st.columns(2)
        new_status = col_s.selectbox("New status", list(ConnectionStatus), format_func=label)
        a, b = (part.strip() for part in chosen.split("|"))
        if col_s.button("Update status"):
            graph.set_connection_status(a, b, new_status)
            st.rerun()
        if col_r.button("Remove connection"):
            graph.remove_connection(a, b)
            st.rerun()

        st.graphviz_chart(graph.to_dot())
        st.caption("Solid = confirmed, dashed = proposed, dotted = uncertain; no arrow = direction unknown.")

    st.markdown("#### Trace and analyse")
    statuses = st.multiselect(
        "Connection statuses to include",
        list(ConnectionStatus),
        default=list(CONFIRMED_ONLY),
        format_func=label,
    )
    directed = st.checkbox("Respect flow direction (known-direction connections only)", True)
    col_from, col_to = st.columns(2)
    path_from = col_from.selectbox("Path from", tags, key="path_from")
    path_to = col_to.selectbox("Path to", tags, index=1, key="path_to")
    if statuses:
        paths = graph.find_paths(path_from, path_to, statuses, directed)
        if paths:
            for path in paths:
                st.write(" -> ".join(path))
        else:
            st.info("No path in the selected connections. This reflects the entered data only.")
        focus = st.selectbox("Upstream / downstream of", tags, key="focus_tag")
        st.write("Upstream:", ", ".join(graph.upstream(focus, statuses)) or "none")
        st.write("Downstream:", ", ".join(graph.downstream(focus, statuses)) or "none")
        groups = graph.connected_components(statuses)
        st.write("Connected groups:", "; ".join(", ".join(g) for g in groups) or "none")
    else:
        st.info("Select at least one status.")


def render_ai_tab(base: Optional[Image.Image]) -> None:
    """Optional Gemini assistant grounded in entered data."""
    graph: ProcessGraph = st.session_state.graph
    st.subheader("AI assistant")
    config = load_config()
    interpreter = GeminiInterpreter(config)
    if interpreter.is_configured:
        st.success(f"Gemini API key detected. Model: {config.model}")
    else:
        st.info("No GEMINI_API_KEY found. The rest of the app works without it. See the README.")
    st.caption(DISCLAIMER)

    context = build_context(graph)
    with st.expander("Data that will be sent to the model"):
        st.code(context or "(nothing entered)", language="text")

    send_image = st.checkbox(
        "Also send the displayed drawing image to Gemini",
        value=False,
        disabled=base is None,
        help="The image leaves your machine. Review the Gemini API terms for data handling.",
    )
    question = st.text_area("Question", placeholder="What are the confirmed upstream items of E-101?")
    if st.button("Ask", disabled=not interpreter.is_configured):
        with st.spinner("Waiting for Gemini"):
            st.session_state.ai_response = interpreter.ask(
                question, context, base if send_image else None
            )

    response = st.session_state.ai_response
    if response is None:
        return
    if response.status is AIStatus.OK:
        st.markdown(response.text)
        st.caption(DISCLAIMER)
    elif response.status in (AIStatus.RATE_LIMITED, AIStatus.NO_CONTEXT, AIStatus.INVALID_INPUT):
        st.warning(response.message)
    elif response.status is AIStatus.NOT_CONFIGURED:
        st.info(response.message)
    else:
        st.error(response.message)


def render_safety_tab() -> None:
    """Educational deviation explorer."""
    graph: ProcessGraph = st.session_state.graph
    st.subheader("Safety explorer")
    st.warning("Educational only. Uses just the verified data you entered.")
    tags = [r.tag for r in graph.equipment()]
    if not tags:
        st.info("Add equipment on the Equipment & Tags tab first.")
        return
    tag = st.selectbox("Equipment", tags, key="safety_tag")
    deviation = st.selectbox(
        "Hypothetical deviation",
        list(Deviation),
        format_func=lambda d: DEVIATIONS[d].label,
    )
    analysis = analyze_deviation(graph, tag, deviation)

    st.markdown("**Potential hazards (generic)**")
    for item in analysis.potential_hazards:
        st.markdown(f"- {item}")
    st.markdown("**Affected scope (confirmed, known-direction connections)**")
    st.write("Upstream:", ", ".join(analysis.upstream) or "none")
    st.write("Downstream:", ", ".join(analysis.downstream) or "none")
    st.markdown("**Safeguards found in verified data**")
    if analysis.safeguards:
        stretch(
            st.dataframe,
            [
                {
                    "Tag": s.tag,
                    "Type": label(s.equipment_type),
                    "Relation": s.relation,
                    "Why listed": s.reason,
                }
                for s in analysis.safeguards
            ],
            hide_index=True,
        )
    else:
        st.write("None found in the entered data.")
    st.markdown("**Missing information**")
    for item in analysis.missing_information:
        st.markdown(f"- {item}")
    st.markdown("**Assumptions requiring engineering review**")
    for item in analysis.assumptions:
        st.markdown(f"- {item}")
    st.caption(analysis.notice)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """Assemble the page."""
    init_state()
    document, page_index, dpi, options = render_sidebar()

    st.title("P&ID Navigator")
    st.write(
        "An AI-assisted workspace for studying Piping and Instrumentation Diagrams. "
        "This early release provides file viewing, preprocessing, a manual process "
        "model, and honest placeholders for automatic recognition."
    )
    with st.expander("What is implemented and what is planned?"):
        stretch(st.dataframe, FEATURES, hide_index=True)

    base: Optional[Image.Image] = None
    processed: Optional[Image.Image] = None
    if document is not None:
        try:
            base = cached_page_image(document, st.session_state.file_hash, page_index, dpi)
            if not options.is_noop:
                processed = preprocess(base, options)
        except DocumentError as exc:
            st.error(str(exc))
        except ValueError as exc:
            st.error(f"Preprocessing failed: {exc}")

    tab_viewer, tab_equipment, tab_flow, tab_ai, tab_safety = st.tabs(
        ["Diagram Viewer", "Equipment & Tags", "Process Flow", "AI Assistant", "Safety Explorer"]
    )
    with tab_viewer:
        render_viewer(base, processed)
    with tab_equipment:
        render_equipment_tab(base, page_index)
    with tab_flow:
        render_flow_tab()
    with tab_ai:
        render_ai_tab(base)
    with tab_safety:
        render_safety_tab()


main()