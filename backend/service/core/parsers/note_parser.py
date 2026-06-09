from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult


class NoteParser:
    supported_types = frozenset({"note", "markdown", "text"})

    async def parse(self, source, **kwargs) -> ParseResult:
        content = source.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        text = (content or "").strip()
        return ParseResult(text=text)


register_parser(NoteParser())
