from dataclasses import dataclass
from typing import Any, Protocol

from service.models import Source


@dataclass
class ParseResult:
    text: str
    title: str | None = None
    metadata: dict[str, Any] | None = None


class ContentParser(Protocol):
    supported_types: frozenset[str]

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        ...
