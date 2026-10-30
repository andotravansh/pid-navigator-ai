"""Safe validation and loading of PDF and image uploads.

All functions work on in-memory bytes. Nothing is written to disk.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PIL import Image, ImageOps

try:  # Newer PyMuPDF exposes the "pymupdf" module name.
    import pymupdf
except ImportError:  # Older releases only provide "fitz".
    import fitz as pymupdf  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Limits and supported formats
# ---------------------------------------------------------------------------
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB per upload
MAX_PDF_PAGES = 500
MAX_IMAGE_PIXELS = 120_000_000  # guards against decompression bombs
MAX_RENDER_DIMENSION = 9000  # longest side (px) of a rendered PDF page
DEFAULT_DPI = 150
MIN_DPI = 50
MAX_DPI = 400

# File extension -> expected content format (verified against file bytes).
EXTENSION_TO_FORMAT = {
    ".pdf": "pdf",
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".webp": "webp",
}
SUPPORTED_EXTENSIONS = tuple(sorted(EXTENSION_TO_FORMAT))


class DocumentKind(str, Enum):
    """High-level document category."""

    PDF = "pdf"
    IMAGE = "image"


class DocumentError(Exception):
    """Raised for user-facing problems while reading or rendering a file."""


@dataclass(frozen=True)
class LoadedDocument:
    """A validated upload held in memory."""

    filename: str
    kind: DocumentKind
    file_format: str
    data: bytes
    page_count: int

    @property
    def size_bytes(self) -> int:
        """Size of the uploaded file in bytes."""
        return len(self.data)


@dataclass(frozen=True)
class LoadResult:
    """Structured result of ``load_document``."""

    document: Optional[LoadedDocument] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True when a document was loaded successfully."""
        return self.document is not None and self.error is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def sniff_format(data: bytes) -> Optional[str]:
    """Identify the file format from magic bytes (not from the extension)."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _extension(filename: str) -> str:
    """Return the lowercase extension including the dot, or an empty string."""
    name = (filename or "").strip().lower()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def validate_upload(
    filename: str, data: bytes, max_bytes: int = MAX_FILE_BYTES
) -> Optional[str]:
    """Check an upload without fully decoding it.

    Returns:
        A human-readable error message, or ``None`` if the file looks valid.
    """
    if not data:
        return "The file is empty."
    if len(data) > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        return f"The file is larger than the {limit_mb:.0f} MB limit."

    extension = _extension(filename)
    if extension not in EXTENSION_TO_FORMAT:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        return f"Unsupported file type '{extension or 'none'}'. Supported: {supported}."

    detected = sniff_format(data)
    if detected is None:
        return "The file content is not a recognised PDF or image format."
    if detected != EXTENSION_TO_FORMAT[extension]:
        return (
            f"The file extension '{extension}' does not match its content "
            f"({detected}). The file may be corrupt or renamed."
        )
    return None


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------
def _open_pdf(data: bytes):
    """Open a PDF from bytes, rejecting corrupt or encrypted files."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several error types.
        raise DocumentError("The PDF could not be opened; it may be corrupt.") from exc
    if getattr(doc, "needs_pass", False):
        doc.close()
        raise DocumentError("The PDF is password-protected and cannot be read.")
    return doc


def get_pdf_page_count(data: bytes) -> int:
    """Return the number of pages in a PDF."""
    doc = _open_pdf(data)
    try:
        return int(doc.page_count)
    finally:
        doc.close()


def render_pdf_page(data: bytes, page_index: int, dpi: int = DEFAULT_DPI) -> Image.Image:
    """Render one PDF page (0-based index) to an RGB PIL image.

    The effective resolution is reduced automatically if the page would
    exceed ``MAX_RENDER_DIMENSION`` pixels on its longest side.
    """
    dpi = max(MIN_DPI, min(MAX_DPI, int(dpi)))
    doc = _open_pdf(data)
    try:
        if not 0 <= page_index < doc.page_count:
            raise DocumentError(
                f"Page {page_index + 1} is out of range (1-{doc.page_count})."
            )
        page = doc.load_page(page_index)
        rect = page.rect
        scale = dpi / 72.0
        longest = max(rect.width, rect.height) * scale
        if longest > MAX_RENDER_DIMENSION:
            scale *= MAX_RENDER_DIMENSION / longest
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError(f"Page {page_index + 1} could not be rendered.") from exc
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def _check_image(data: bytes) -> None:
    """Verify that image bytes decode and are not unreasonably large."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            width, height = probe.size
            if width * height > MAX_IMAGE_PIXELS:
                raise DocumentError("The image has too many pixels to open safely.")
            probe.verify()
    except DocumentError:
        raise
    except Exception as exc:  # Pillow raises several error types.
        raise DocumentError("The image could not be read; it may be corrupt.") from exc


def load_image_bytes(data: bytes) -> Image.Image:
    """Decode image bytes into an RGB image (EXIF-rotated, white background)."""
    _check_image(data)
    try:
        with Image.open(io.BytesIO(data)) as raw:
            image = ImageOps.exif_transpose(raw)
            if image.mode in ("RGBA", "LA", "P"):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                return background
            return image.convert("RGB")
    except Exception as exc:
        raise DocumentError("The image could not be decoded.") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_document(
    filename: str, data: bytes, max_bytes: int = MAX_FILE_BYTES
) -> LoadResult:
    """Validate an upload and return a structured result (never raises)."""
    error = validate_upload(filename, data, max_bytes)
    if error:
        return LoadResult(error=error)

    file_format = sniff_format(data) or ""
    try:
        if file_format == "pdf":
            page_count = get_pdf_page_count(data)
            if page_count < 1:
                return LoadResult(error="The PDF contains no pages.")
            if page_count > MAX_PDF_PAGES:
                return LoadResult(
                    error=f"The PDF has {page_count} pages; the limit is {MAX_PDF_PAGES}."
                )
            kind = DocumentKind.PDF
        else:
            _check_image(data)
            page_count = 1
            kind = DocumentKind.IMAGE
    except DocumentError as exc:
        return LoadResult(error=str(exc))

    document = LoadedDocument(
        filename=filename,
        kind=kind,
        file_format=file_format,
        data=data,
        page_count=page_count,
    )
    return LoadResult(document=document)


def get_page_image(
    document: LoadedDocument, page_index: int = 0, dpi: int = DEFAULT_DPI
) -> Image.Image:
    """Return the requested page of a loaded document as an RGB image."""
    if document.kind is DocumentKind.PDF:
        return render_pdf_page(document.data, page_index, dpi)
    if page_index != 0:
        raise DocumentError("Image files have only one page.")
    return load_image_bytes(document.data)