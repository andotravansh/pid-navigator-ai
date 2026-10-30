"""Tests for engineering list logic. No network or API key needed."""

from modules.engineering_lists import (
    ALL_SCHEMA_KEYS,
    EQUIPMENT_LIST,
    INSTRUMENT_LIST,
    LINE_LIST,
    count_by_type,
    equipment_rows,
    group_instrument_loops,
    instrument_rows,
    split_records,
    table_data,
    to_csv_bytes,
    valve_rows,
)
from modules.pid_parser import EquipmentRecord, EquipmentType, Evidence, EvidenceSource


def rec(tag, kind, verified=True, description=""):
    return EquipmentRecord(
        tag=tag,
        equipment_type=kind,
        verified=verified,
        description=description,
        evidence=[Evidence(source=EvidenceSource.USER_ENTRY)],
    )


RECORDS = [
    rec("P-101", EquipmentType.PUMP),
    rec("XV-101", EquipmentType.VALVE, description="Isolation"),
    rec("PSV-101", EquipmentType.RELIEF_DEVICE),
    rec("FT-101", EquipmentType.INSTRUMENT),
    rec("FIC-101", EquipmentType.INSTRUMENT),
    rec("LT-200", EquipmentType.INSTRUMENT),
    rec("NOTATAG", EquipmentType.INSTRUMENT),
]


def test_line_list_has_required_columns():
    for column in ("Line No.", "Service", "Nominal Diameter", "Insulation",
                   "Material / Spec", "Remarks"):
        assert column in LINE_LIST.columns


def test_schema_keys_are_unique():
    assert len(ALL_SCHEMA_KEYS) == len(set(ALL_SCHEMA_KEYS))


def test_split_records_by_category():
    parts = split_records(RECORDS)
    assert [r.tag for r in parts["equipment"]] == ["P-101"]
    assert [r.tag for r in parts["valve"]] == ["XV-101", "PSV-101"]
    assert len(parts["instrument"]) == 4


def test_empty_table_keeps_headers():
    data = table_data(LINE_LIST.columns, [])
    assert list(data) == list(LINE_LIST.columns)
    assert all(values == [] for values in data.values())


def test_rows_fill_known_columns_only():
    row = equipment_rows([RECORDS[0]])[0]
    data = table_data(EQUIPMENT_LIST.columns, [row])
    assert data["Tag"] == ["P-101"]
    assert data["Capacity / Size"] == [""]  # never guessed
    assert data["Source"] == ["user entry"]


def test_valve_rows_use_remarks_for_description():
    assert valve_rows([RECORDS[1]])[0]["Remarks"] == "Isolation"


def test_instrument_rows_parse_tag_syntax():
    row = instrument_rows([RECORDS[3]])[0]
    assert row["ISA Letters"] == "FT"
    assert row["Measured Variable"] == "Flow"
    assert row["Loop No."] == "101"
    assert instrument_rows([RECORDS[6]])[0]["ISA Letters"] == ""
    assert set(table_data(INSTRUMENT_LIST.columns, [row])) == set(INSTRUMENT_LIST.columns)


def test_group_instrument_loops():
    groups, unparsed = group_instrument_loops(RECORDS)
    assert [(g.loop_id, g.tags) for g in groups] == [
        ("F-101", ("FIC-101", "FT-101")),
        ("L-200", ("LT-200",)),
    ]
    assert unparsed == ["NOTATAG"]


def test_count_by_type_is_sorted():
    assert count_by_type(RECORDS) == {
        "Instrument": 4, "Pump": 1, "Relief Device": 1, "Valve": 1,
    }


def test_csv_has_bom_header_and_blocks_formula_injection():
    rows = [{"Tag": "=CMD()", "Type": "Pump"}, {"Tag": "-1", "Type": "ok"}]
    raw = to_csv_bytes(("Tag", "Type"), rows)
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").splitlines()
    assert text[0] == "Tag,Type"
    assert text[1] == "'=CMD(),Pump"
    assert text[2] == "'-1,ok"
