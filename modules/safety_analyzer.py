"""Educational hypothetical-deviation explorer.

It reports only what the verified model supports. It never concludes that
a system is safe and never invents safeguards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from modules.pid_parser import (
    ConnectionStatus,
    EquipmentRecord,
    EquipmentType,
    parse_instrument_tag,
)
from modules.process_graph import ProcessGraph, UnknownTagError

EDUCATIONAL_NOTICE = (
    "Educational exploration only. This is not a HAZOP, LOPA, or safety "
    "assessment. Absence of a safeguard here means it was not found in the "
    "entered data, not that none exists."
)


class Deviation(str, Enum):
    """Hypothetical process deviations (HAZOP-style guidewords)."""

    NO_FLOW = "no_flow"
    REVERSE_FLOW = "reverse_flow"
    HIGH_PRESSURE = "high_pressure"
    HIGH_LEVEL = "high_level"
    HIGH_TEMPERATURE = "high_temperature"


@dataclass(frozen=True)
class DeviationInfo:
    """Generic educational description of a deviation."""

    label: str
    hazards: tuple[str, ...]
    variables: frozenset[str]  # ISA measured variables relevant to detection
    equipment_types: frozenset[EquipmentType]  # device types that mitigate it


DEVIATIONS: dict[Deviation, DeviationInfo] = {
    Deviation.NO_FLOW: DeviationInfo(
        "No flow",
        (
            "Loss of cooling, heating, or feed to downstream equipment",
            "Pump damage from running dry or dead-heading",
            "Process upset or off-specification product",
        ),
        frozenset({"Flow"}),
        frozenset(),
    ),
    Deviation.REVERSE_FLOW: DeviationInfo(
        "Reverse flow",
        (
            "Back-flow into equipment not designed for that service",
            "Mixing of incompatible streams",
            "Reverse rotation of rotating equipment",
        ),
        frozenset({"Flow"}),
        frozenset({EquipmentType.CHECK_VALVE}),
    ),
    Deviation.HIGH_PRESSURE: DeviationInfo(
        "High pressure",
        (
            "Overpressure beyond design limits and loss of containment",
            "Release of hazardous material",
            "Relief discharge to an unsuitable location",
        ),
        frozenset({"Pressure"}),
        frozenset({EquipmentType.RELIEF_DEVICE}),
    ),
    Deviation.HIGH_LEVEL: DeviationInfo(
        "High level",
        (
            "Overfilling and liquid carry-over into vapour or gas lines",
            "Liquid release through vents or overflows",
        ),
        frozenset({"Level"}),
        frozenset(),
    ),
    Deviation.HIGH_TEMPERATURE: DeviationInfo(
        "High temperature",
        (
            "Overheating beyond material or design temperature",
            "Runaway reaction or decomposition",
            "Pressure rise from thermal expansion of trapped liquid",
        ),
        frozenset({"Temperature"}),
        frozenset(),
    ),
}


@dataclass(frozen=True)
class SafeguardFinding:
    """A verified item in scope that may relate to the deviation."""

    tag: str
    equipment_type: EquipmentType
    relation: str
    reason: str


@dataclass
class DeviationAnalysis:
    """Structured result separating hazards, safeguards, gaps, and assumptions."""

    equipment_tag: str
    deviation: Deviation
    potential_hazards: list[str]
    upstream: list[str]
    downstream: list[str]
    safeguards: list[SafeguardFinding]
    missing_information: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    notice: str = EDUCATIONAL_NOTICE


def _match_reason(record: EquipmentRecord, info: DeviationInfo) -> Optional[str]:
    """Explain why a record might relate to the deviation, or return None."""
    if record.equipment_type in info.equipment_types:
        return f"Entered as a {record.equipment_type.value.replace('_', ' ')}."
    if record.equipment_type is EquipmentType.INSTRUMENT:
        parsed = parse_instrument_tag(record.tag)
        if parsed and parsed.measured_variable in info.variables:
            return (
                f"Instrument tag suggests {parsed.measured_variable.lower()} "
                f"(letters '{parsed.isa_letters}'). Its function, set point, and "
                "action must be confirmed on the drawing."
            )
    return None


def _scope(graph: ProcessGraph, tag: str) -> dict[str, str]:
    """Tags considered in scope, with how each relates to the equipment."""
    scope = {tag: "same item"}
    for other in graph.upstream(tag):
        scope.setdefault(other, "upstream (confirmed, known direction)")
    for other in graph.downstream(tag):
        scope.setdefault(other, "downstream (confirmed, known direction)")
    for other in graph.neighbors(tag):
        scope.setdefault(other, "adjacent (confirmed connection)")
    return scope


def analyze_deviation(
    graph: ProcessGraph, equipment_tag: str, deviation: Deviation
) -> DeviationAnalysis:
    """Explore a hypothetical deviation using only confirmed connections.

    Raises:
        UnknownTagError: if the tag is not in the graph.
    """
    record = graph.get_equipment(equipment_tag)
    if record is None:
        raise UnknownTagError(f"Unknown tag: {equipment_tag}")
    info = DEVIATIONS[deviation]
    tag = record.tag

    scope = _scope(graph, tag)
    safeguards: list[SafeguardFinding] = []
    unverified: list[str] = []
    for scoped_tag, relation in sorted(scope.items()):
        scoped = graph.get_equipment(scoped_tag)
        if scoped is None:
            continue
        reason = _match_reason(scoped, info)
        if not reason:
            continue
        if scoped.verified:
            safeguards.append(
                SafeguardFinding(scoped.tag, scoped.equipment_type, relation, reason)
            )
        else:
            unverified.append(scoped.tag)

    missing: list[str] = []
    if len(scope) == 1:
        missing.append(
            f"No confirmed connections to {tag}; upstream/downstream effects "
            "cannot be assessed."
        )
    unconfirmed = [
        c
        for c in graph.connections()
        if tag in (c.source_tag, c.target_tag) and c.status is not ConnectionStatus.CONFIRMED
    ]
    if unconfirmed:
        missing.append(
            f"{len(unconfirmed)} proposed/uncertain connection(s) touch {tag} and "
            "were excluded from this analysis."
        )
    if not safeguards:
        missing.append(
            f"No verified item matching '{info.label.lower()}' safeguards was found in "
            "scope. This does not mean none exist."
        )
    missing.append(
        "Operating and design conditions, set points, relief sizing, and control "
        "logic are not available from this model."
    )

    assumptions = [
        "Hazard descriptions are generic educational statements, not derived from "
        "this drawing.",
        "Only user-verified items are listed as safeguards; each still requires "
        "engineering review of its actual function.",
    ]
    if unverified:
        assumptions.append(
            "Possibly relevant but unverified items were not counted: "
            + ", ".join(sorted(unverified))
            + "."
        )

    return DeviationAnalysis(
        equipment_tag=tag,
        deviation=deviation,
        potential_hazards=list(info.hazards),
        upstream=graph.upstream(tag),
        downstream=graph.downstream(tag),
        safeguards=safeguards,
        missing_information=missing,
        assumptions=assumptions,
    )