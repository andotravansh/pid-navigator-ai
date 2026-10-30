"""Structured records and the (not yet implemented) P&ID extraction interface.

No automatic recognition exists yet. ``extract_from_image`` returns an
explicit NOT_IMPLEMENTED status instead of inventing detections.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional, Protocol

from PIL import Image
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class EquipmentType(str, Enum):
    """Kinds of items that can appear as graph nodes."""

    PUMP = "pump"
    COMPRESSOR = "compressor"
    TANK = "tank"
    VESSEL = "vessel"
    REACTOR = "reactor"
    HEAT_EXCHANGER = "heat_exchanger"
    COLUMN = "column"
    VALVE = "valve"
    CHECK_VALVE = "check_valve"
    RELIEF_DEVICE = "relief_device"
    INSTRUMENT = "instrument"
    OTHER = "other"


class ConnectionStatus(str, Enum):
    """How far a connection has been verified."""

    CONFIRMED = "confirmed"
    PROPOSED = "proposed"
    UNCERTAIN = "uncertain"


class EvidenceSource(str, Enum):
    """Where a piece of extracted information came from."""

    USER_ENTRY = "user_entry"
    OCR = "ocr"
    SYMBOL_DETECTION = "symbol_detection"
    AI_SUGGESTION = "ai_suggestion"


class ExtractionStatus(str, Enum):
    """Outcome of an extraction attempt."""

    NOT_IMPLEMENTED = "not_implemented"
    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_tag(tag: str) -> str:
    """Normalise a tag: trim, collapse whitespace, upper-case.

    Raises:
        ValueError: if the tag is not a non-empty string.
    """
    if not isinstance(tag, str):
        raise ValueError("Tag must be a string.")
    cleaned = " ".join(tag.split()).upper()
    if not cleaned:
        raise ValueError("Tag must not be empty.")
    return cleaned


# ---------------------------------------------------------------------------
# Evidence and records
# ---------------------------------------------------------------------------
class BoundingBox(BaseModel):
    """A rectangle on a rendered page, in pixels of the rendered image."""

    page: int = Field(ge=0)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(ge=0)
    height: float = Field(ge=0)
    render_dpi: Optional[int] = None


class Evidence(BaseModel):
    """Why we believe a record exists, and how sure we are."""

    source: EvidenceSource
    bbox: Optional[BoundingBox] = None
    note: str = ""
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class EquipmentRecord(BaseModel):
    """A piece of equipment, valve, or instrument identified by its tag."""

    tag: str
    equipment_type: EquipmentType = EquipmentType.OTHER
    description: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    verified: bool = False  # True only after a human confirmed it on the drawing

    @field_validator("tag")
    @classmethod
    def _normalise_tag(cls, value: str) -> str:
        return normalize_tag(value)


class InstrumentTag(BaseModel):
    """An instrument label parsed from text (syntactic interpretation only)."""

    raw_text: str
    isa_letters: str
    measured_variable: Optional[str] = None
    loop_number: str
    suffix: str = ""
    evidence: list[Evidence] = Field(default_factory=list)


class CandidateConnection(BaseModel):
    """A possible line between two tagged items."""

    source_tag: str
    target_tag: str
    direction_known: bool = False  # source -> target only meaningful if True
    status: ConnectionStatus = ConnectionStatus.PROPOSED
    line_label: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    notes: str = ""

    @field_validator("source_tag", "target_tag")
    @classmethod
    def _normalise_tags(cls, value: str) -> str:
        return normalize_tag(value)

    @model_validator(mode="after")
    def _no_self_connection(self) -> "CandidateConnection":
        if self.source_tag == self.target_tag:
            raise ValueError("A connection cannot join an item to itself.")
        return self


class ExtractionResult(BaseModel):
    """Everything an extractor reports, including its honest status."""

    status: ExtractionStatus
    message: str
    equipment: list[EquipmentRecord] = Field(default_factory=list)
    instruments: list[InstrumentTag] = Field(default_factory=list)
    connections: list[CandidateConnection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ISA-style tag parsing (syntactic only)
# ---------------------------------------------------------------------------
# Common first-letter meanings from ISA-5.1 style tagging (subset).
ISA_FIRST_LETTERS = {
    "A": "Analysis",
    "F": "Flow",
    "H": "Hand",
    "J": "Power",
    "L": "Level",
    "P": "Pressure",
    "Q": "Quantity",
    "S": "Speed",
    "T": "Temperature",
    "V": "Vibration",
    "W": "Weight",
    "Z": "Position",
}
_INSTRUMENT_PATTERN = re.compile(r"^([A-Za-z]{2,5})[\s\-]*(\d{1,6})([A-Za-z]{0,2})$")


def parse_instrument_tag(text: str) -> Optional[InstrumentTag]:
    """Split text like ``FIC-101`` into letters and loop number.

    This is purely syntactic. It cannot tell an instrument from other
    tags with the same shape (for example ``TK-101`` is a tank, not a
    temperature instrument), so callers must supply context.

    Returns:
        An ``InstrumentTag`` or ``None`` if the text does not fit the pattern.
    """
    if not isinstance(text, str):
        return None
    match = _INSTRUMENT_PATTERN.match(text.strip())
    if not match:
        return None
    letters, loop, suffix = match.groups()
    letters = letters.upper()
    return InstrumentTag(
        raw_text=text.strip(),
        isa_letters=letters,
        measured_variable=ISA_FIRST_LETTERS.get(letters[0]),
        loop_number=loop,
        suffix=suffix.upper(),
    )


# ---------------------------------------------------------------------------
# Extraction interface
# ---------------------------------------------------------------------------
class PIDExtractor(Protocol):
    """Interface that future OCR / vision / AI extractors must implement."""

    name: str

    def extract(self, image: Image.Image, page_index: int) -> ExtractionResult:
        """Return structured detections for one rendered page."""


class PlaceholderExtractor:
    """Honest stand-in: reports that automatic extraction is unavailable."""

    name = "placeholder"

    def extract(self, image: Image.Image, page_index: int) -> ExtractionResult:
        """Return NOT_IMPLEMENTED without inspecting the image."""
        return ExtractionResult(
            status=ExtractionStatus.NOT_IMPLEMENTED,
            message=(
                "Automatic extraction of equipment, tags, and connections is not "
                "implemented yet. No detections were made. Use manual entry to "
                "build a verified model of the drawing."
            ),
            warnings=[
                "Planned: OCR for tags, symbol detection, and line tracing, each "
                "returning evidence and confidence for human review."
            ],
        )


def extract_from_image(
    image: Image.Image,
    page_index: int = 0,
    extractor: Optional[PIDExtractor] = None,
) -> ExtractionResult:
    """Run an extractor (the placeholder by default) on a rendered page."""
    if not isinstance(image, Image.Image):
        raise TypeError("image must be a PIL.Image.Image.")
    if page_index < 0:
        raise ValueError("page_index must be >= 0.")
    return (extractor or PlaceholderExtractor()).extract(image, page_index)