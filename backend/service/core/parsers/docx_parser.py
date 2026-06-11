try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None  # type: ignore[assignment, misc]

from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult
from service.core.storage import resolve_file_path


class DocxParser:
    supported_types = frozenset({"docx"})

    async def parse(self, source, **kwargs) -> ParseResult:
        if Document is None:
            raise ValueError("python-docx is not installed; cannot parse DOCX files")

        if not source.filename:
            raise ValueError("DOCX source is missing filename")

        file_path = resolve_file_path(source.filename)
        document = Document(str(file_path))

        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]

        title = None
        if paragraphs:
            title = paragraphs[0]

        text = "\n\n".join(paragraphs)

        return ParseResult(text=text, title=title)


register_parser(DocxParser())
