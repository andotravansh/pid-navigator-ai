"""Headless UI tests using Streamlit's AppTest. No browser, key or internet needed."""

import io
import re
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from modules.document_reader import load_document
from modules.pid_parser import (
    CandidateConnection,
    ConnectionStatus,
    EquipmentRecord,
    EquipmentType,
)
from ui.pages.workflow import themed_dot

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

PAGES = [
    "dashboard", "upload", "workspace", "analysis", "lists", "workflow",
    "control", "quantity", "assistant", "safety", "export",
]


def png_bytes(size=(300, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def page_script(module_name: str) -> None:
    import importlib

    from ui.state import init_state
    from ui.theme import apply_theme

    init_state()
    apply_theme()
    importlib.import_module(f"ui.pages.{module_name}").render()


def upload_script(filename: str, data: bytes) -> None:
    from types import SimpleNamespace

    import streamlit as st

    from ui.state import handle_upload, init_state

    init_state()
    handle_upload(SimpleNamespace(name=filename, getvalue=lambda: data))
    st.session_state["ran"] = True


def html_of(at: AppTest) -> str:
    return "".join(element.proto.body for element in at.get("html"))


def new_page(name: str) -> AppTest:
    return AppTest.from_function(page_script, args=(name,), default_timeout=30).run()


def seed(at: AppTest) -> AppTest:
    at.session_state["document"] = load_document("demo.png", png_bytes()).document
    at.session_state["file_hash"] = "test-hash"
    graph = at.session_state["graph"]
    for tag, kind in [
        ("T-101", EquipmentType.TANK),
        ("P-101", EquipmentType.PUMP),
        ("XV-101", EquipmentType.VALVE),
        ("PSV-101", EquipmentType.RELIEF_DEVICE),
        ("FT-101", EquipmentType.INSTRUMENT),
        ("FIC-101", EquipmentType.INSTRUMENT),
    ]:
        graph.add_equipment(EquipmentRecord(tag=tag, equipment_type=kind, verified=True))
    graph.add_connection(CandidateConnection(
        source_tag="T-101", target_tag="P-101", direction_known=True,
        status=ConnectionStatus.CONFIRMED))
    graph.add_connection(CandidateConnection(
        source_tag="P-101", target_tag="XV-101", direction_known=False,
        status=ConnectionStatus.PROPOSED))
    return at.run()


@pytest.mark.parametrize("name", PAGES)
def test_page_renders_with_no_data(name):
    at = new_page(name)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("name", PAGES)
def test_page_renders_with_seeded_data(name):
    at = seed(new_page(name))
    assert not at.exception, [e.value for e in at.exception]


def test_full_app_starts_on_dashboard():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not at.exception
    assert "Welcome to P&amp;ID Navigator" in html_of(at)


def test_dashboard_shows_zeros_without_data():
    at = new_page("dashboard")
    assert re.findall(r'pn-metric-value">([^<]*)<', html_of(at)) == ["0", "0", "0", "0"]
    assert "No activity yet" in html_of(at)


def test_dashboard_counts_only_entered_items():
    at = seed(new_page("dashboard"))
    values = re.findall(r'pn-metric-value">([^<]*)<', html_of(at))
    # drawings, equipment (tank + pump), lines (never extracted), valves (valve + relief)
    assert values == ["1", "2", "0", "2"]


def test_lines_card_never_claims_extraction():
    assert "Extraction not implemented" in html_of(seed(new_page("dashboard")))


def test_workspace_without_drawing_shows_empty_state():
    assert "No drawing to inspect" in html_of(new_page("workspace"))


def test_workspace_zoom_and_enhancement_controls_work():
    at = seed(new_page("workspace"))
    at.slider(key="ws_zoom").set_value(3.0).run()
    assert not at.exception
    at.checkbox(key="pp_gray").check().run()
    assert not at.exception
    assert at.radio(key="ws_view").options == ["Original", "Preprocessed"]
    at.radio(key="ws_view").set_value("Preprocessed").run()
    assert not at.exception


def test_lists_show_empty_states_and_schema_columns():
    at = new_page("lists")
    assert not at.exception
    assert "No valves entered" in html_of(at)
    assert len(at.dataframe) == 5
    line_columns = list(at.dataframe[0].value.columns)
    for column in ("Line No.", "Service", "Nominal Diameter", "Insulation",
                   "Material / Spec", "Remarks"):
        assert column in line_columns
    assert all(len(frame.value) == 0 for frame in at.dataframe[:1])


def test_lists_route_items_by_type():
    at = seed(new_page("lists"))
    sizes = [len(frame.value) for frame in at.dataframe]
    # line, valve (valve + relief), control valve, equipment (tank + pump), instrument (2)
    assert sizes == [0, 2, 0, 2, 2]


def test_manual_entry_adds_item_and_logs_activity():
    at = new_page("lists")
    at.text_input[0].input("p-201")
    next(b for b in at.button if b.label == "Add item").click()
    at.run()
    assert not at.exception
    graph = at.session_state["graph"]
    assert graph.get_equipment("P-201") is not None
    assert any("P-201" in message for _, message in at.session_state["activity"])


def test_duplicate_manual_entry_is_reported_not_crashed():
    at = seed(new_page("lists"))
    at.text_input[0].input("t-101")
    next(b for b in at.button if b.label == "Add item").click()
    at.run()
    assert not at.exception
    assert any("already exists" in e.value for e in at.error)


def test_workflow_needs_two_items():
    assert "Add at least two items" in html_of(new_page("workflow"))


def test_workflow_renders_dark_themed_graph():
    at = seed(new_page("workflow"))
    assert not at.exception
    charts = at.get("graphviz_chart")
    assert len(charts) == 1
    assert 'bgcolor="transparent"' in charts[0].proto.spec


def test_themed_dot_keeps_graph_valid():
    dot = themed_dot('digraph PID {\n  rankdir=LR;\n}')
    assert dot.startswith("digraph PID {")
    assert "fontcolor" in dot and dot.count("digraph PID") == 1


def test_planned_pages_do_not_present_results():
    for name in ("analysis", "control", "quantity"):
        at = seed(new_page(name))
        assert "pn-planned" in html_of(at)
        assert "Not available yet" in html_of(at)


def test_extraction_button_reports_not_implemented():
    at = seed(new_page("analysis"))
    next(b for b in at.button if b.label == "Run automatic extraction").click()
    at.run()
    assert not at.exception
    assert any("not implemented" in i.value.lower() for i in at.info)


def test_control_page_groups_instruments_by_tag_syntax_only():
    at = seed(new_page("control"))
    loops = at.dataframe[0].value
    assert list(loops["Loop"]) == ["F-101"]
    assert "naming heuristic" in " ".join(c.value for c in at.caption)


def test_export_disabled_until_data_exists():
    at = new_page("export")
    assert all(b.disabled for b in at.get("download_button"))
    at = seed(new_page("export"))
    enabled = [b.proto.label for b in at.get("download_button") if not b.proto.disabled]
    assert len(enabled) == 3


def test_assistant_works_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = new_page("assistant")
    assert not at.exception


def test_upload_accepts_valid_png_and_logs():
    at = AppTest.from_function(upload_script, args=("plan.png", png_bytes()), default_timeout=30).run()
    assert not at.exception
    assert at.session_state["document"].filename == "plan.png"
    assert at.session_state["load_error"] is None
    assert "Loaded plan.png" in at.session_state["activity"][-1][1]


def test_upload_rejects_corrupt_file_with_message():
    at = AppTest.from_function(upload_script, args=("bad.png", b"\x89PNG\r\n\x1a\nxx"), default_timeout=30).run()
    assert not at.exception
    assert at.session_state["document"] is None
    assert at.session_state["load_error"]


def test_upload_rejects_unsupported_type():
    at = AppTest.from_function(upload_script, args=("notes.txt", b"hello"), default_timeout=30).run()
    assert at.session_state["document"] is None
    assert "Unsupported" in at.session_state["load_error"]


def test_new_upload_clears_previous_manual_model():
    at = AppTest.from_function(upload_script, args=("a.png", png_bytes()), default_timeout=30).run()
    at.session_state["graph"].add_equipment(EquipmentRecord(tag="P-1"))
    at.session_state["file_hash"] = "something-else"  # simulate a different file
    at.run()
    assert len(at.session_state["graph"]) == 0
