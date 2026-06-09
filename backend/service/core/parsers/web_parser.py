import httpx
from bs4 import BeautifulSoup

from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult


class WebParser:
    source_type = "link"

    async def parse(self, raw: str | bytes, **kwargs) -> ParseResult:
        mode = kwargs.get("mode", "link")
        if mode == "crawl":
            return await self._parse_crawl(raw, **kwargs)
        return await self._parse_link(raw, **kwargs)

    async def _parse_link(self, raw: str | bytes, **kwargs) -> ParseResult:
        url = raw if isinstance(raw, str) else raw.decode("utf-8")
        async with httpx.AsyncClient(follow_redirects=True, timeout=12) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        content = " ".join(soup.get_text(" ").split())

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        return ParseResult(content=content, title=title)

    async def _parse_crawl(self, raw: str | bytes, **kwargs) -> ParseResult:
        raise NotImplementedError("Crawl mode is not yet implemented")


register_parser(WebParser())
