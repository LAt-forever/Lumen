import pytest

from service.core.parsers import get_parser, register_parser
from service.core.parsers.base import ParseResult
from service.core.parsers.note_parser import NoteParser
from service.core.parsers.web_parser import WebParser


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
    result = await parser.parse("  hello world  ")
    assert result == ParseResult(content="hello world")


@pytest.mark.asyncio
async def test_note_parser_handles_none():
    parser = NoteParser()
    result = await parser.parse(None)
    assert result == ParseResult(content="")


@pytest.mark.asyncio
async def test_note_parser_handles_bytes():
    parser = NoteParser()
    result = await parser.parse(b"  byte content  ")
    assert result == ParseResult(content="byte content")


def test_register_parser_adds_to_registry():
    class DummyParser:
        source_type = "dummy"

        async def parse(self, raw, **kwargs):
            return ParseResult(content="dummy")

    register_parser(DummyParser())
    parser = get_parser("dummy")
    assert isinstance(parser, DummyParser)
