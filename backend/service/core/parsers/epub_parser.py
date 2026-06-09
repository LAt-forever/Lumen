try:
    import ebooklib
    from ebooklib import epub
except Exception:  # pragma: no cover
    ebooklib = None  # type: ignore[assignment]
    epub = None  # type: ignore[assignment]

from bs4 import BeautifulSoup

from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult
from service.core.storage import resolve_file_path


class EpubParser:
    supported_types = frozenset({"epub"})

    async def parse(self, source, **kwargs) -> ParseResult:
        if not source.filename:
            raise ValueError("EPUB source is missing filename")

        file_path = resolve_file_path(source.filename)
        book = epub.read_epub(str(file_path))

        title = None
        metadata = book.get_metadata("DC", "title")
        if metadata:
            title = metadata[0][0]

        texts: list[str] = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                page_text = soup.get_text(" ", strip=True)
                if page_text:
                    texts.append(page_text)

        text = "\n\n".join(texts)

        return ParseResult(text=text, title=title)


register_parser(EpubParser())
