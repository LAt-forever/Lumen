from service.core.parsers.base import ParseResult
from service.core.parsers import register_parser


class NoteParser:
    source_type = "note"

    async def parse(self, raw: str | bytes, **kwargs) -> ParseResult:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        content = (raw or "").strip()
        return ParseResult(content=content)


register_parser(NoteParser())
