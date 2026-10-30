"""Tests for upload validation and loading. No network or API key needed."""

import io

import pytest
from PIL import Image

from modules.document_reader import (
    DocumentError,
    DocumentKind,
    get_page_image,
    load_document,
    render_pdf_page,
    sniff_format,
    validate_upload,
)

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf  # type: ignore[no-redef]


def make_png(size=(120, 80)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def make_pdf(pages: int = 2) -> bytes:
    doc = pymupdf.open()
    for number in range(pages):
        page = doc.new_page(width=200, height=300)
        page.insert_text((20, 50), f"P-10{number}")
    data = doc.tobytes()
    doc.close()
    return data


def test_sniff_format_detects_known_types():
    assert sniff_format(make_png()) == "png"
    assert sniff_format(make_pdf(1)) == "pdf"
    assert sniff_format(b"hello") is None


def test_validate_rejects_empty_file():
    assert validate_upload("a.png", b"") is not None


def test_validate_rejects_unsupported_extension():
    assert "Unsupported" in validate_upload("notes.txt", b"abc")


def test_validate_rejects_oversized_file():
    assert "larger" in validate_upload("a.png", make_png(), max_bytes=10)


def test_validate_rejects_extension_content_mismatch():
    assert validate_upload("fake.pdf", make_png()) is not None


def test_validate_accepts_valid_png():
    assert validate_upload("ok.png", make_png()) is None


def test_load_png_document():
    result = load_document("diagram.png", make_png())
    assert result.ok
    assert result.document.kind is DocumentKind.IMAGE
    assert result.document.page_count == 1
    assert get_page_image(result.document).size == (120, 80)


def test_load_pdf_document_and_render():
    result = load_document("diagram.pdf", make_pdf(2))
    assert result.ok
    assert result.document.kind is DocumentKind.PDF
    assert result.document.page_count == 2
    image = render_pdf_page(result.document.data, 1, dpi=72)
    assert image.width > 0 and image.height > 0


def test_pdf_page_out_of_range():
    with pytest.raises(DocumentError):
        render_pdf_page(make_pdf(1), 5)


def test_corrupt_pdf_is_rejected():
    result = load_document("bad.pdf", b"%PDF-1.4\nthis is not a real pdf")
    assert not result.ok
    assert result.error


def test_corrupt_png_is_rejected():
    result = load_document("bad.png", b"\x89PNG\r\n\x1a\nnot an image")
    assert not result.ok


def test_image_has_single_page():
    document = load_document("a.png", make_png()).document
    with pytest.raises(DocumentError):
        get_page_image(document, page_index=1)