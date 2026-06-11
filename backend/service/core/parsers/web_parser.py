import logging
from collections import deque
from urllib.parse import urldefrag, urlparse

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

logger = logging.getLogger(__name__)


class WebParser:
    supported_types = frozenset({"link", "web_crawl"})

    async def parse(self, source, **kwargs) -> ParseResult:
        if source.source_type == "web_crawl":
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

    def _normalize_url(self, url: str) -> str:
        """Strip fragment and normalize trailing slash for deduplication."""
        clean, _ = urldefrag(url)
        parsed = urlparse(clean)
        # Normalize path trailing slash for dedup (e.g. /page and /page/)
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    async def _parse_crawl(self, source, **kwargs) -> ParseResult:
        if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
            return await self._parse_link(source, **kwargs)

        start_url = source.url or ""
        if not start_url:
            return await self._parse_link(source, **kwargs)

        max_depth = max(1, min(3, kwargs.get("max_depth", 2)))
        max_pages = max(1, min(50, kwargs.get("max_pages", 10)))
        same_domain_only = kwargs.get("same_domain_only", True)

        start_parsed = urlparse(start_url)
        start_domain = start_parsed.netloc

        visited: set[str] = set()
        pages: list[dict] = []
        queue: deque[tuple[str, int]] = deque([(start_url, 0)])

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                while queue and len(pages) < max_pages:
                    url, depth = queue.popleft()
                    norm_url = self._normalize_url(url)
                    if norm_url in visited or depth > max_depth:
                        continue
                    visited.add(norm_url)

                    page = None
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
                                norm_link = self._normalize_url(link)
                                if norm_link not in visited:
                                    queue.append((link, depth + 1))

                    except Exception as exc:
                        logger.warning("Crawl failed for %s: %s", url, exc)
                    finally:
                        if page is not None:
                            try:
                                await page.close()
                            except Exception:
                                pass
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
