import io
import os
import tempfile
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject

from service.core.parsers.pdf_parser import PdfParser
from service.core.parsers.base import ParseResult


class FakeSource:
    def __init__(self, content=None, url=None, filename=None, title="", source_type=""):
        self.content = content
        self.url = url
        self.filename = filename
        self.title = title
        self.source_type = source_type


def _make_text_pdf(text: str) -> bytes:
    """Create a minimal in-memory PDF containing selectable text."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    # Add a simple /Contents stream that draws text using the PDF operator Tj
    content_stream = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET".encode("latin-1")
    from pypdf.generic import StreamObject
    stream = StreamObject()
    stream._data = content_stream
    stream.update({NameObject("/Length"): NumberObject(len(content_stream))})
    contents_ref = writer._add_object(stream)
    page[NameObject("/Contents")] = contents_ref

    # Add a minimal resource dictionary with a font
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    resources = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): font_ref,
        }),
    })
    page[NameObject("/Resources")] = writer._add_object(resources)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()


@pytest.fixture
def parser():
    return PdfParser()


def test_supported_types(parser):
    assert parser.supported_types == frozenset({"pdf"})


@pytest.mark.asyncio
async def test_parse_missing_filename_raises(parser):
    source = FakeSource(filename=None)
    with pytest.raises(ValueError, match="missing filename"):
        await parser.parse(source)


@pytest.mark.asyncio
async def test_parse_real_text_pdf(parser, tmp_path: Path, monkeypatch):
    """Test parsing a real selectable-text PDF."""
    # Set up the upload root to be our temp path so resolve_file_path works
    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    pdf_bytes = _make_text_pdf("Hello from PDF")
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_bytes)

    source = FakeSource(filename="test.pdf")
    result = await parser.parse(source)
    assert isinstance(result, ParseResult)
    assert "Hello from PDF" in result.text


@pytest.mark.asyncio
async def test_parse_empty_pdf_raises(parser, tmp_path: Path, monkeypatch):
    """Test that a PDF with no text and no OCR raises ValueError."""
    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    # Create a blank PDF with no text content
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)

    pdf_path = tmp_path / "blank.pdf"
    pdf_path.write_bytes(buf.read())

    source = FakeSource(filename="blank.pdf")
    with pytest.raises(ValueError, match="no extractable text"):
        await parser.parse(source)
