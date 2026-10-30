"""Single source of truth for what is implemented, experimental or planned."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    """Maturity of a feature."""

    IMPLEMENTED = "implemented"
    EXPERIMENTAL = "experimental"
    PLANNED = "planned"


@dataclass(frozen=True)
class Feature:
    """One user-visible capability."""

    name: str
    section: str
    status: Status


FEATURES: tuple[Feature, ...] = (
    Feature("Upload and validation (PDF, PNG, JPG, WebP)", "Upload P&ID", Status.IMPLEMENTED),
    Feature("PDF page selection and rendering", "Diagram Workspace", Status.IMPLEMENTED),
    Feature("Zoom and pan inspection", "Diagram Workspace", Status.IMPLEMENTED),
    Feature("Image enhancement (OpenCV)", "Diagram Workspace", Status.IMPLEMENTED),
    Feature("Manual equipment, valve and instrument entry", "Engineering Lists", Status.IMPLEMENTED),
    Feature("Manual connections, paths, upstream and downstream", "Process Workflow", Status.IMPLEMENTED),
    Feature("Educational deviation explorer (entered data only)", "Safety Explorer", Status.IMPLEMENTED),
    Feature("CSV download of manually entered lists", "Export & Reports", Status.IMPLEMENTED),
    Feature("AI answers grounded in entered data (needs Gemini key)", "AI Assistant", Status.EXPERIMENTAL),
    Feature("Instrument loop grouping from tag syntax", "Control Philosophy", Status.EXPERIMENTAL),
    Feature("OCR and tag recognition", "Diagram Analysis", Status.PLANNED),
    Feature("Symbol detection and component counting", "Diagram Analysis", Status.PLANNED),
    Feature("Line tracing and connection detection", "Diagram Analysis", Status.PLANNED),
    Feature("Detection overlays on the drawing", "Diagram Workspace", Status.PLANNED),
    Feature("Automatic line, valve and equipment lists", "Engineering Lists", Status.PLANNED),
    Feature("Control-loop and control-logic interpretation", "Control Philosophy", Status.PLANNED),
    Feature("Quantity and material estimation", "Quantity Estimation", Status.PLANNED),
    Feature("Excel and PDF reports", "Export & Reports", Status.PLANNED),
    Feature("AutoCAD-compatible DXF output", "Export & Reports", Status.PLANNED),
)


def count_by_status() -> dict[Status, int]:
    """Number of features per status."""
    return {s: sum(1 for f in FEATURES if f.status is s) for s in Status}
