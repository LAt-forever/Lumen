import pytest

from service.core.parsers import get_parser, register_parser
from service.core.parsers.base import ParseResult
from service.core.parsers.note_parser import NoteParser
from service.core.parsers.web_parser import WebParser


class FakeSource:
    def __init__(self, content=None, url=None, filename=None, title="", source_type=""):
        self.content = content
        self.url = url
        self.filename = filename
        self.title = title
        self.source_type = source_type


def test_get_parser_returns_note_parser():
    parser = get_parser("note")
    assert isinstance(parser, NoteParser)


def test_get_parser_returns_web_parser():
    parser = get_parser("link")
    assert isinstance(parser, WebParser)


def test_get_parser_unknown_raises():
    with pytest.raises(ValueError, match="No parser registered"):
        get_parser("nonexistent")


@pytest.mark.asyncio
async def test_note_parser_returns_stripped_content():
    parser = NoteParser()
    source = FakeSource(content="  hello world  ")
    result = await parser.parse(source)
    assert result == ParseResult(text="hello world")


@pytest.mark.asyncio
async def test_note_parser_handles_none():
    parser = NoteParser()
    source = FakeSource(content=None)
    result = await parser.parse(source)
    assert result == ParseResult(text="")


@pytest.mark.asyncio
async def test_note_parser_handles_bytes():
    parser = NoteParser()
    source = FakeSource(content=b"  byte content  ")
    result = await parser.parse(source)
    assert result == ParseResult(text="byte content")


def test_register_parser_adds_to_registry():
    class DummyParser:
        supported_types = frozenset({"dummy"})

        async def parse(self, source, **kwargs):
            return ParseResult(text="dummy")

    register_parser(DummyParser())
    parser = get_parser("dummy")
    assert isinstance(parser, DummyParser)
