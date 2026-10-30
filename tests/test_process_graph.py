"""Tests for graph operations. No network or API key needed."""

import pytest
from pydantic import ValidationError

from modules.pid_parser import (
    CandidateConnection,
    ConnectionStatus,
    EquipmentRecord,
    EquipmentType,
)
from modules.process_graph import (
    ALL_STATUSES,
    DuplicateConnectionError,
    DuplicateTagError,
    ProcessGraph,
    UnknownConnectionError,
    UnknownTagError,
)

CONFIRMED = ConnectionStatus.CONFIRMED
PROPOSED = ConnectionStatus.PROPOSED


def conn(a, b, status=CONFIRMED, directed=True):
    return CandidateConnection(
        source_tag=a, target_tag=b, direction_known=directed, status=status
    )


@pytest.fixture
def graph() -> ProcessGraph:
    g = ProcessGraph()
    for tag, kind in [
        ("T-101", EquipmentType.TANK),
        ("P-101", EquipmentType.PUMP),
        ("E-101", EquipmentType.HEAT_EXCHANGER),
        ("R-101", EquipmentType.REACTOR),
    ]:
        g.add_equipment(EquipmentRecord(tag=tag, equipment_type=kind))
    g.add_connection(conn("T-101", "P-101"))
    g.add_connection(conn("P-101", "E-101"))
    return g


def test_lookup_is_case_insensitive(graph):
    assert graph.get_equipment(" p-101 ").tag == "P-101"
    assert graph.get_equipment("X-999") is None
    assert "t-101" in graph


def test_duplicate_tag_rejected(graph):
    with pytest.raises(DuplicateTagError):
        graph.add_equipment(EquipmentRecord(tag="p-101"))


def test_connection_requires_existing_tags(graph):
    with pytest.raises(UnknownTagError):
        graph.add_connection(conn("P-101", "X-999"))


def test_duplicate_connection_rejected(graph):
    with pytest.raises(DuplicateConnectionError):
        graph.add_connection(conn("T-101", "P-101"))


def test_self_connection_rejected():
    with pytest.raises(ValidationError):
        conn("P-101", "p-101")


def test_forward_path_found(graph):
    assert graph.find_paths("t-101", "e-101") == [["T-101", "P-101", "E-101"]]


def test_backward_path_blocked_when_directed(graph):
    assert graph.find_paths("E-101", "T-101") == []
    assert graph.find_paths("E-101", "T-101", directed=False) == [
        ["E-101", "P-101", "T-101"]
    ]


def test_unconfirmed_connections_excluded_by_default(graph):
    graph.add_connection(conn("E-101", "R-101", status=PROPOSED))
    assert graph.find_paths("T-101", "R-101") == []
    assert graph.find_paths("T-101", "R-101", statuses=ALL_STATUSES) == [
        ["T-101", "P-101", "E-101", "R-101"]
    ]


def test_unknown_direction_not_followed_in_directed_mode(graph):
    graph.add_connection(conn("E-101", "R-101", directed=False))
    assert graph.find_paths("E-101", "R-101") == []
    assert graph.find_paths("E-101", "R-101", directed=False) == [["E-101", "R-101"]]
    assert "R-101" not in graph.downstream("E-101")
    assert "R-101" in graph.neighbors("E-101")


def test_upstream_and_downstream(graph):
    assert graph.downstream("T-101") == ["E-101", "P-101"]
    assert graph.upstream("E-101") == ["P-101", "T-101"]


def test_disconnected_components(graph):
    assert graph.connected_components() == [["E-101", "P-101", "T-101"], ["R-101"]]


def test_remove_equipment_removes_its_connections(graph):
    graph.remove_equipment("P-101")
    assert graph.connections() == []
    assert "P-101" not in graph


def test_remove_and_update_connection(graph):
    updated = graph.set_connection_status("T-101", "P-101", ConnectionStatus.UNCERTAIN)
    assert updated.status is ConnectionStatus.UNCERTAIN
    assert graph.find_paths("T-101", "P-101") == []
    graph.remove_connection("T-101", "P-101")
    with pytest.raises(UnknownConnectionError):
        graph.remove_connection("T-101", "P-101")


def test_dot_output_contains_tags_and_styles(graph):
    graph.add_connection(conn("E-101", "R-101", status=PROPOSED))
    dot = graph.to_dot()
    assert '"T-101"' in dot and "style=dashed" in dot and "style=solid" in dot


def test_summary_counts(graph):
    assert graph.summary() == {
        "equipment": 4,
        "confirmed": 2,
        "proposed": 0,
        "uncertain": 0,
    }