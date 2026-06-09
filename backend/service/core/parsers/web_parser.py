import httpx
from bs4 import BeautifulSoup

from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None  # type: ignore[misc,assignment]


class WebParser:
    supported_types = frozenset({"link"})

    async def parse(self, source, **kwargs) -> ParseResult:
        mode = kwargs.get("mode", "link")
        if mode == "crawl":
            return await self._parse_crawl(source, **kwargs)
        return await self._parse_link(source, **kwargs)

    async def _parse_link(self, source, **kwargs) -> ParseResult:
        url = source.url or ""
        async with httpx.AsyncClient(follow_redirects=True, timeout=12) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ").split())

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        return ParseResult(text=text, title=title)

    async def _parse_crawl(self, source, **kwargs) -> ParseResult:
        if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
            return await self._parse_link(source, **kwargs)

        start_url = source.url or ""
        if not start_url:
            return await self._parse_link(source, **kwargs)

        max_depth = max(1, min(3, kwargs.get("max_depth", 2)))
        max_pages = max(1, min(50, kwargs.get("max_pages", 10)))
        same_domain_only = kwargs.get("same_domain_only", True)

        from urllib.parse import urlparse

        start_parsed = urlparse(start_url)
        start_domain = start_parsed.netloc

        visited: set[str] = set()
        pages: list[dict] = []
        queue: list[tuple[str, int]] = [(start_url, 0)]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                while queue and len(pages) < max_pages:
                    url, depth = queue.pop(0)
                    if url in visited or depth > max_depth:
                        continue
                    visited.add(url)

                    try:
                        page = await browser.new_page()
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        title = await page.title()

                        await page.evaluate(
                            """() => {
                                const selectors = ['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'];
                                selectors.forEach(sel => {
                                    document.querySelectorAll(sel).forEach(el => el.remove());
                                });
                            }"""
                        )
                        body_text = await page.evaluate(
                            "() => document.body ? document.body.innerText : ''"
                        )
                        text = " ".join(body_text.split())

                        pages.append({"url": url, "title": title, "text": text})

                        if depth < max_depth and len(pages) < max_pages:
                            raw_links = await page.eval_on_selector_all(
                                "a[href]",
                                "elements => elements.map(el => el.href)",
                            )
                            for link in raw_links:
                                parsed = urlparse(link)
                                if parsed.scheme not in ("http", "https"):
                                    continue
                                if same_domain_only and parsed.netloc != start_domain:
                                    continue
                                if link not in visited:
                                    queue.append((link, depth + 1))

                        await page.close()
                    except Exception:
                        continue
            finally:
                await browser.close()

        if not pages:
            return await self._parse_link(source, **kwargs)

        parts = []
        for page in pages:
            parts.append(f"# {page['title']}\n\n{page['text']}\n\n---\n来源: {page['url']}")

        combined_text = "\n\n".join(parts)
        return ParseResult(text=combined_text, title=pages[0]["title"])


register_parser(WebParser())
