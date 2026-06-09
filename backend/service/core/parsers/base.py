from dataclasses import dataclass
from typing import Protocol


@dataclass
class ParseResult:
    content: str
    title: str | None = None
    metadata: dict | None = None


class ContentParser(Protocol):
    source_type: str

    async def parse(self, raw: str | bytes, **kwargs) -> ParseResult:
        ...
