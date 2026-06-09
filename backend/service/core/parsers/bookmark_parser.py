from bs4 import BeautifulSoup

from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult


class BookmarkParser:
    supported_types = frozenset({"bookmark"})

    async def parse(self, source, **kwargs) -> ParseResult:
        html = source.content or ""
        if isinstance(html, bytes):
            html = html.decode("utf-8")

        soup = BeautifulSoup(html, "html.parser")
        bookmarks = []
        seen_urls = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "").strip()
            title = a_tag.get_text(strip=True)
            if not href or not title:
                continue

            # Deduplicate: same URL + title combination
            key = (href, title)
            if key in seen_urls:
                continue
            seen_urls.add(key)

            # Look for a <dd> that immediately follows this <a> tag
            dd = None
            for sibling in a_tag.next_siblings:
                if getattr(sibling, "name", None) == "dd":
                    dd = sibling
                    break
                if getattr(sibling, "name", None) is not None:
                    break

            description = dd.get_text(strip=True) if dd else None

            bookmarks.append({
                "title": title,
                "url": href,
                "description": description,
            })

        if not bookmarks:
            raise ValueError("No bookmarks found in HTML content")

        parts = []
        for bm in bookmarks:
            part = f"标题: {bm['title']}\n链接: {bm['url']}"
            if bm["description"]:
                part += f"\n描述: {bm['description']}"
            parts.append(part)

        text = "\n\n---\n\n".join(parts)
        return ParseResult(
            text=text,
            metadata={"bookmark_count": len(bookmarks)},
        )


register_parser(BookmarkParser())
