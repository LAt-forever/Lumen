from pathlib import Path

import pytest
from ebooklib import epub

from service.core.parsers.epub_parser import EpubParser
from service.core.parsers.base import ParseResult


class FakeSource:
    def __init__(self, content=None, url=None, filename=None, title="", source_type=""):
        self.content = content
        self.url = url
        self.filename = filename
        self.title = title
        self.source_type = source_type


@pytest.fixture
def parser():
    return EpubParser()


def test_supported_types(parser):
    assert parser.supported_types == frozenset({"epub"})


@pytest.mark.asyncio
async def test_parse_missing_filename_raises(parser):
    source = FakeSource(filename=None)
    with pytest.raises(ValueError, match="missing filename"):
        await parser.parse(source)


@pytest.mark.asyncio
async def test_parse_epub(parser, tmp_path: Path, monkeypatch):
    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title("Test Book Title")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="chap_1.xhtml", lang="en")
    c1.content = "<html><body><h1>Chapter 1</h1><p>First paragraph.</p></body></html>"
    book.add_item(c1)

    c2 = epub.EpubHtml(title="Chapter 2", file_name="chap_2.xhtml", lang="en")
    c2.content = "<html><body><h1>Chapter 2</h1><p>Second paragraph.</p></body></html>"
    book.add_item(c2)

    book.toc = (epub.Link("chap_1.xhtml", "Chapter 1", "c1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1, c2]

    epub_path = tmp_path / "test.epub"
    epub.write_epub(str(epub_path), book)

    source = FakeSource(filename="test.epub")
    result = await parser.parse(source)
    assert isinstance(result, ParseResult)
    assert result.title == "Test Book Title"
    assert "Chapter 1" in result.text
    assert "First paragraph." in result.text
    assert "Chapter 2" in result.text
    assert "Second paragraph." in result.text


@pytest.mark.asyncio
async def test_parse_epub_strips_scripts_and_styles(parser, tmp_path: Path, monkeypatch):
    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    book = epub.EpubBook()
    book.set_identifier("test-id-2")
    book.set_title("Styled Book")
    book.set_language("en")

    c1 = epub.EpubHtml(title="Chapter 1", file_name="chap_1.xhtml", lang="en")
    c1.content = (
        "<html><body>"
        "<style>body{color:red}</style>"
        "<script>alert('xss')</script>"
        "<p>Clean text.</p>"
        "<noscript>No JS</noscript>"
        "</body></html>"
    )
    book.add_item(c1)
    book.add_item(epub.EpubNcx())
    book.spine = [c1]

    epub_path = tmp_path / "styled.epub"
    epub.write_epub(str(epub_path), book)

    source = FakeSource(filename="styled.epub")
    result = await parser.parse(source)
    assert "Clean text." in result.text
    assert "alert" not in result.text
    assert "No JS" not in result.text
    assert "color:red" not in result.text
