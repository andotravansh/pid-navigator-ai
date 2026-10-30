"""NetworkX-backed process graph that keeps verification status explicit.

Rules:
* Connections are never inferred; they must be added explicitly.
* Traversals default to CONFIRMED connections only.
* Directed traversal follows only connections whose direction is known.
"""

from __future__ import annotations

from itertools import islice
from typing import Iterable, Optional

import networkx as nx

from modules.pid_parser import (
    CandidateConnection,
    ConnectionStatus,
    EquipmentRecord,
    normalize_tag,
)

CONFIRMED_ONLY: tuple[ConnectionStatus, ...] = (ConnectionStatus.CONFIRMED,)
ALL_STATUSES: tuple[ConnectionStatus, ...] = tuple(ConnectionStatus)

_EDGE_STYLE = {
    ConnectionStatus.CONFIRMED: "solid",
    ConnectionStatus.PROPOSED: "dashed",
    ConnectionStatus.UNCERTAIN: "dotted",
}


class GraphError(Exception):
    """Base class for graph problems."""


class DuplicateTagError(GraphError):
    """A tag is already present."""


class UnknownTagError(GraphError):
    """A tag is not present."""


class DuplicateConnectionError(GraphError):
    """The connection (or its reverse) already exists."""


class UnknownConnectionError(GraphError):
    """The connection does not exist."""


def _escape_dot(text: str) -> str:
    """Escape text for use inside a double-quoted DOT string."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


class ProcessGraph:
    """Equipment nodes plus connections with verification status."""

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

    # -- basics -------------------------------------------------------------
    def __len__(self) -> int:
        return self._g.number_of_nodes()

    def __contains__(self, tag: object) -> bool:
        if not isinstance(tag, str):
            return False
        try:
            return normalize_tag(tag) in self._g
        except ValueError:
            return False

    def _require(self, tag: str) -> str:
        """Normalise a tag and ensure it exists."""
        try:
            key = normalize_tag(tag)
        except ValueError as exc:
            raise UnknownTagError(str(exc)) from exc
        if key not in self._g:
            raise UnknownTagError(f"Unknown tag: {key}")
        return key

    # -- equipment ------------------------------------------------------------
    def add_equipment(self, record: EquipmentRecord) -> None:
        """Add an equipment node; tags must be unique."""
        if record.tag in self._g:
            raise DuplicateTagError(f"Tag already exists: {record.tag}")
        self._g.add_node(record.tag, record=record)

    def remove_equipment(self, tag: str) -> None:
        """Remove a node and every connection attached to it."""
        self._g.remove_node(self._require(tag))

    def get_equipment(self, tag: str) -> Optional[EquipmentRecord]:
        """Look up equipment by tag (case-insensitive); ``None`` if absent."""
        try:
            key = normalize_tag(tag)
        except ValueError:
            return None
        data = self._g.nodes.get(key)
        return data["record"] if data else None

    def equipment(self) -> list[EquipmentRecord]:
        """All equipment records sorted by tag."""
        items = sorted(self._g.nodes(data=True), key=lambda item: item[0])
        return [data["record"] for _, data in items]

    # -- connections ------------------------------------------------------------
    def _edge_key(self, a: str, b: str) -> Optional[tuple[str, str]]:
        """Locate the stored edge joining a and b, if any."""
        if self._g.has_edge(a, b):
            return (a, b)
        if self._g.has_edge(b, a) and not self._g.edges[b, a]["connection"].direction_known:
            return (b, a)
        return None

    def add_connection(self, connection: CandidateConnection) -> None:
        """Add a connection between two existing tags."""
        source = self._require(connection.source_tag)
        target = self._require(connection.target_tag)
        if self._g.has_edge(source, target):
            raise DuplicateConnectionError(f"Connection exists: {source} -> {target}")
        if self._g.has_edge(target, source):
            existing = self._g.edges[target, source]["connection"]
            if not (existing.direction_known and connection.direction_known):
                raise DuplicateConnectionError(
                    f"{source} and {target} are already connected."
                )
        self._g.add_edge(source, target, connection=connection)

    def get_connection(self, a: str, b: str) -> Optional[CandidateConnection]:
        """Return the connection joining two tags, if present."""
        key = self._edge_key(self._require(a), self._require(b))
        return self._g.edges[key]["connection"] if key else None

    def remove_connection(self, a: str, b: str) -> None:
        """Remove the connection joining two tags."""
        key = self._edge_key(self._require(a), self._require(b))
        if key is None:
            raise UnknownConnectionError(f"No connection between {a} and {b}.")
        self._g.remove_edge(*key)

    def set_connection_status(
        self, a: str, b: str, status: ConnectionStatus
    ) -> CandidateConnection:
        """Change the verification status of a connection."""
        key = self._edge_key(self._require(a), self._require(b))
        if key is None:
            raise UnknownConnectionError(f"No connection between {a} and {b}.")
        updated = self._g.edges[key]["connection"].model_copy(update={"status": status})
        self._g.edges[key]["connection"] = updated
        return updated

    def connections(
        self, statuses: Iterable[ConnectionStatus] = ALL_STATUSES
    ) -> list[CandidateConnection]:
        """All connections whose status is in ``statuses``."""
        allowed = set(statuses)
        found = [
            data["connection"]
            for _, _, data in self._g.edges(data=True)
            if data["connection"].status in allowed
        ]
        return sorted(found, key=lambda c: (c.source_tag, c.target_tag))

    # -- views and traversal ------------------------------------------------------
    def _view(self, statuses: Iterable[ConnectionStatus], directed: bool) -> nx.Graph:
        """Build a filtered graph. Directed views keep known-direction edges only."""
        allowed = set(statuses)
        view: nx.Graph = nx.DiGraph() if directed else nx.Graph()
        view.add_nodes_from(self._g.nodes)
        for u, v, data in self._g.edges(data=True):
            connection = data["connection"]
            if connection.status not in allowed:
                continue
            if directed and not connection.direction_known:
                continue
            view.add_edge(u, v)
        return view

    def find_paths(
        self,
        source: str,
        target: str,
        statuses: Iterable[ConnectionStatus] = CONFIRMED_ONLY,
        directed: bool = True,
        max_paths: int = 20,
        cutoff: Optional[int] = None,
    ) -> list[list[str]]:
        """Find simple paths (shortest first) between two tags."""
        start = self._require(source)
        end = self._require(target)
        if start == end:
            return [[start]]
        view = self._view(statuses, directed)
        paths = list(
            islice(nx.all_simple_paths(view, start, end, cutoff=cutoff), max_paths)
        )
        return sorted(paths, key=len)

    def downstream(
        self, tag: str, statuses: Iterable[ConnectionStatus] = CONFIRMED_ONLY
    ) -> list[str]:
        """Tags reachable by following known-direction connections forward."""
        key = self._require(tag)
        return sorted(nx.descendants(self._view(statuses, True), key))

    def upstream(
        self, tag: str, statuses: Iterable[ConnectionStatus] = CONFIRMED_ONLY
    ) -> list[str]:
        """Tags that reach this tag by known-direction connections."""
        key = self._require(tag)
        return sorted(nx.ancestors(self._view(statuses, True), key))

    def neighbors(
        self, tag: str, statuses: Iterable[ConnectionStatus] = CONFIRMED_ONLY
    ) -> list[str]:
        """Directly connected tags, ignoring direction."""
        key = self._require(tag)
        return sorted(self._view(statuses, False).neighbors(key))

    def connected_components(
        self, statuses: Iterable[ConnectionStatus] = CONFIRMED_ONLY
    ) -> list[list[str]]:
        """Groups of tags linked by the chosen connections (isolated nodes included)."""
        groups = [sorted(c) for c in nx.connected_components(self._view(statuses, False))]
        return sorted(groups, key=lambda g: (-len(g), g))

    # -- reporting ----------------------------------------------------------------
    def summary(self) -> dict[str, int]:
        """Counts of nodes and connections by status."""
        counts = {status.value: 0 for status in ConnectionStatus}
        for connection in self.connections():
            counts[connection.status.value] += 1
        return {"equipment": len(self), **counts}

    def to_dot(self, statuses: Iterable[ConnectionStatus] = ALL_STATUSES) -> str:
        """Graphviz DOT text. Solid=confirmed, dashed=proposed, dotted=uncertain."""
        lines = [
            "digraph PID {",
            "  rankdir=LR;",
            '  node [shape=box, style="rounded"];',
        ]
        for record in self.equipment():
            tag = _escape_dot(record.tag)
            kind = _escape_dot(record.equipment_type.value)
            lines.append(f'  "{tag}" [label="{tag}\\n{kind}"];')
        for c in self.connections(statuses):
            attrs = [f"style={_EDGE_STYLE[c.status]}"]
            if not c.direction_known:
                attrs.append("dir=none")
            if c.line_label:
                attrs.append(f'label="{_escape_dot(c.line_label)}"')
            lines.append(
                f'  "{_escape_dot(c.source_tag)}" -> "{_escape_dot(c.target_tag)}" '
                f'[{", ".join(attrs)}];'
            )
        lines.append("}")
        return "\n".join(lines)