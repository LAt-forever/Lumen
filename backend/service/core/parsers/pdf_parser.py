from pypdf import PdfReader

from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult


class PdfParser:
    source_type = "pdf"

    async def parse(self, raw: str | bytes, **kwargs) -> ParseResult:
        path = raw if isinstance(raw, str) else raw.decode("utf-8")
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        content = "\n\n".join(page.strip() for page in pages if page.strip())
        return ParseResult(content=content)


register_parser(PdfParser())
