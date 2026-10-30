"""Engineering list schemas and row builders (pure logic, no Streamlit).

The tables defined here describe the *target* structure of P&ID take-off
lists. Rows are built only from records the user entered; columns that no
extractor can fill yet stay blank rather than being guessed.
"""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from modules.pid_parser import EquipmentRecord, EquipmentType, parse_instrument_tag

Row = Mapping[str, Any]


@dataclass(frozen=True)
class TableSpec:
    """Name and column layout of one engineering table."""

    key: str
    title: str
    columns: tuple[str, ...]
    description: str


LINE_LIST = TableSpec(
    "line_list",
    "Line List",
    ("Line No.", "Service", "Nominal Diameter", "From", "To",
     "Insulation", "Material / Spec", "Remarks"),
    "Every process line with its service, size, insulation and piping class.",
)
VALVE_LIST = TableSpec(
    "valve_list",
    "Valve List",
    ("Tag", "Valve Type", "Line No.", "Size", "Actuation",
     "Normal Position", "Fail Position", "Remarks"),
    "Manual, check, relief and on/off valves.",
)
CONTROL_VALVE_LIST = TableSpec(
    "control_valve_list",
    "Control Valve List",
    ("Tag", "Service / Line", "Size", "Cv", "Actuator",
     "Fail Action", "Controlling Loop", "Remarks"),
    "Valves driven by a controller, with the loop that positions them.",
)
EQUIPMENT_LIST = TableSpec(
    "equipment_list",
    "Equipment List",
    ("Tag", "Type", "Description", "Capacity / Size",
     "Design Conditions", "Verified", "Source"),
    "Pumps, vessels, exchangers, columns and other tagged equipment.",
)
INSTRUMENT_LIST = TableSpec(
    "instrument_list",
    "Instrument List",
    ("Tag", "ISA Letters", "Measured Variable", "Loop No.",
     "Function", "Location", "Verified", "Source"),
    "Transmitters, indicators, controllers and switches.",
)
CONTROL_LOOP_TABLE = TableSpec(
    "control_loops",
    "Control loops",
    ("Loop ID", "Measured Variable", "Sensor / Transmitter", "Controller",
     "Final Element", "Set Point", "Action", "Mode", "Source"),
    "Each loop from measurement to final element.",
)
INTERLOCK_TABLE = TableSpec(
    "interlocks",
    "Interlocks and trips",
    ("ID", "Initiating Condition", "Logic", "Action / Final Element",
     "Reset", "Source"),
    "Safety and protective functions shown on the drawing.",
)
ALARM_TABLE = TableSpec(
    "alarms",
    "Alarms",
    ("Tag", "Alarm Type", "Set Point", "Operator Response", "Source"),
    "Alarm points such as high, high-high, low and low-low.",
)
QUANTITY_TABLE = TableSpec(
    "quantities",
    "Bill of quantities",
    ("Item", "Category", "Size / Spec", "Quantity", "Unit", "Source"),
    "Counted components and estimated materials.",
)
DETECTION_TABLE = TableSpec(
    "detections",
    "Detections",
    ("Text / Symbol", "Class", "Confidence", "Page", "Evidence"),
    "Items found by OCR or symbol detection, each with evidence.",
)

ALL_TABLES: tuple[TableSpec, ...] = (
    LINE_LIST, VALVE_LIST, CONTROL_VALVE_LIST, EQUIPMENT_LIST, INSTRUMENT_LIST,
    CONTROL_LOOP_TABLE, INTERLOCK_TABLE, ALARM_TABLE, QUANTITY_TABLE, DETECTION_TABLE,
)
ALL_SCHEMA_KEYS: tuple[str, ...] = tuple(table.key for table in ALL_TABLES)

EQUIPMENT_TYPES = frozenset({
    EquipmentType.PUMP, EquipmentType.COMPRESSOR, EquipmentType.TANK,
    EquipmentType.VESSEL, EquipmentType.REACTOR, EquipmentType.HEAT_EXCHANGER,
    EquipmentType.COLUMN, EquipmentType.OTHER,
})
VALVE_TYPES = frozenset({
    EquipmentType.VALVE, EquipmentType.CHECK_VALVE, EquipmentType.RELIEF_DEVICE,
})
INSTRUMENT_TYPES = frozenset({EquipmentType.INSTRUMENT})


# ---------------------------------------------------------------------------
# Categorising records
# ---------------------------------------------------------------------------
def category_of(record: EquipmentRecord) -> str:
    """Return 'valve', 'instrument' or 'equipment' for a record."""
    if record.equipment_type in VALVE_TYPES:
        return "valve"
    if record.equipment_type in INSTRUMENT_TYPES:
        return "instrument"
    return "equipment"


def split_records(records: Iterable[EquipmentRecord]) -> dict[str, list[EquipmentRecord]]:
    """Group records into equipment, valve and instrument lists."""
    parts: dict[str, list[EquipmentRecord]] = {
        "equipment": [], "valve": [], "instrument": [],
    }
    for record in records:
        parts[category_of(record)].append(record)
    return parts


def count_by_type(records: Iterable[EquipmentRecord]) -> dict[str, int]:
    """Count records per equipment type label, sorted by label."""
    counter = Counter(_type_label(r.equipment_type) for r in records)
    return dict(sorted(counter.items()))


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------
def _type_label(kind: EquipmentType) -> str:
    return kind.value.replace("_", " ").title()


def _source_label(record: EquipmentRecord) -> str:
    sources = sorted({e.source.value.replace("_", " ") for e in record.evidence})
    return ", ".join(sources) or "unspecified"


def _yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def equipment_rows(records: Iterable[EquipmentRecord]) -> list[dict[str, Any]]:
    """Rows for the equipment list (unknown columns stay blank)."""
    return [
        {
            "Tag": r.tag,
            "Type": _type_label(r.equipment_type),
            "Description": r.description,
            "Verified": _yes_no(r.verified),
            "Source": _source_label(r),
        }
        for r in records
    ]


def valve_rows(records: Iterable[EquipmentRecord]) -> list[dict[str, Any]]:
    """Rows for the valve list; the description is shown under Remarks."""
    return [
        {
            "Tag": r.tag,
            "Valve Type": _type_label(r.equipment_type),
            "Remarks": r.description,
        }
        for r in records
    ]


def instrument_rows(records: Iterable[EquipmentRecord]) -> list[dict[str, Any]]:
    """Rows for the instrument list, with tag letters parsed syntactically."""
    rows: list[dict[str, Any]] = []
    for r in records:
        parsed = parse_instrument_tag(r.tag)
        rows.append({
            "Tag": r.tag,
            "ISA Letters": parsed.isa_letters if parsed else "",
            "Measured Variable": (parsed.measured_variable or "") if parsed else "",
            "Loop No.": f"{parsed.loop_number}{parsed.suffix}" if parsed else "",
            "Function": r.description,
            "Verified": _yes_no(r.verified),
            "Source": _source_label(r),
        })
    return rows


def table_data(columns: Sequence[str], rows: Sequence[Row]) -> dict[str, list[Any]]:
    """Column-oriented data for a table; empty rows still keep every header."""
    return {column: [row.get(column, "") for row in rows] for column in columns}


# ---------------------------------------------------------------------------
# Instrument loop grouping (syntax only)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoopGroup:
    """Instruments whose tags share a first letter and loop number."""

    loop_id: str
    measured_variable: str
    tags: tuple[str, ...]


def group_instrument_loops(
    records: Iterable[EquipmentRecord],
) -> tuple[list[LoopGroup], list[str]]:
    """Group instrument-type records by tag syntax, e.g. FT-101 and FIC-101.

    This is a naming heuristic, not a verified control loop. Returns the
    groups and the tags that did not fit the instrument pattern.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    variables: dict[str, str] = {}
    unparsed: list[str] = []
    for record in records:
        if record.equipment_type not in INSTRUMENT_TYPES:
            continue
        parsed = parse_instrument_tag(record.tag)
        if parsed is None:
            unparsed.append(record.tag)
            continue
        loop_id = f"{parsed.isa_letters[0]}-{parsed.loop_number}"
        groups[loop_id].append(record.tag)
        variables[loop_id] = parsed.measured_variable or "Unknown"
    result = [
        LoopGroup(loop_id, variables[loop_id], tuple(sorted(tags)))
        for loop_id, tags in sorted(groups.items())
    ]
    return result, sorted(unparsed)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: Any) -> str:
    """Neutralise spreadsheet formula injection by prefixing an apostrophe."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def to_csv_bytes(columns: Sequence[str], rows: Sequence[Row]) -> bytes:
    """UTF-8 CSV (with BOM so Excel detects the encoding)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_safe_cell(row.get(column, "")) for column in columns])
    return buffer.getvalue().encode("utf-8-sig")
