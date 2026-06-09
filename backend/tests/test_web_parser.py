import pytest

from service.core.parsers.base import ParseResult
from service.core.parsers.web_parser import PLAYWRIGHT_AVAILABLE, WebParser


class FakeSource:
    def __init__(self, content=None, url=None, filename=None, title="", source_type=""):
        self.content = content
        self.url = url
        self.filename = filename
        self.title = title
        self.source_type = source_type


@pytest.fixture
def parser():
    return WebParser()


def test_supported_types(parser):
    assert parser.supported_types == frozenset({"link"})


@pytest.mark.asyncio
async def test_parse_link_missing_url_raises(parser):
    source = FakeSource(url=None)
    with pytest.raises(Exception):
        await parser.parse(source)


@pytest.mark.asyncio
async def test_parse_crawl_without_playwright_fallback(parser, monkeypatch):
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", False
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", None
    )

    calls = []

    async def mock_parse_link(source, **kwargs):
        calls.append("fallback")
        return ParseResult(text="fallback", title="Fallback")

    monkeypatch.setattr(parser, "_parse_link", mock_parse_link)

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(source)
    assert result.text == "fallback"
    assert result.title == "Fallback"
    assert calls == ["fallback"]


@pytest.mark.asyncio
async def test_parse_crawl_empty_url_fallback(parser, monkeypatch):
    calls = []

    async def mock_parse_link(source, **kwargs):
        calls.append("fallback")
        return ParseResult(text="fallback", title="Fallback")

    monkeypatch.setattr(parser, "_parse_link", mock_parse_link)

    source = FakeSource(url="")
    result = await parser._parse_crawl(source)
    assert result.text == "fallback"
    assert result.title == "Fallback"
    assert calls == ["fallback"]


@pytest.mark.asyncio
async def test_parse_crawl_params_clamped(parser, monkeypatch):
    def fake_playwright():
        class FakeBrowser:
            async def new_page(self):
                class FakePage:
                    async def goto(self, *a, **k):
                        pass
                    async def title(self):
                        return "Title"
                    async def evaluate(self, *a, **k):
                        return ""
                    async def eval_on_selector_all(self, *a, **k):
                        return []
                    async def close(self):
                        pass
                return FakePage()
            async def close(self):
                pass

        class FakeP:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            @property
            def chromium(self):
                class FakeChromium:
                    async def launch(self, **k):
                        return FakeBrowser()
                return FakeChromium()

        return FakeP()

    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", fake_playwright
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", True
    )

    async def mock_parse_link(source, **kwargs):
        return ParseResult(text="fallback", title="Fallback")

    monkeypatch.setattr(parser, "_parse_link", mock_parse_link)

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(source, max_depth=5, max_pages=100)
    assert isinstance(result, ParseResult)


@pytest.mark.asyncio
async def test_parse_crawl_successful_pages(parser, monkeypatch):
    def fake_playwright():
        class FakeBrowser:
            async def new_page(self):
                class FakePage:
                    async def goto(self, *a, **k):
                        pass
                    async def title(self):
                        return "Test Page"
                    async def evaluate(self, *a, **k):
                        return "Some body text here"
                    async def eval_on_selector_all(self, *a, **k):
                        return []
                    async def close(self):
                        pass
                return FakePage()
            async def close(self):
                pass

        class FakeP:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            @property
            def chromium(self):
                class FakeChromium:
                    async def launch(self, **k):
                        return FakeBrowser()
                return FakeChromium()

        return FakeP()

    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", fake_playwright
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", True
    )

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(source, max_depth=1, max_pages=5)
    assert isinstance(result, ParseResult)
    assert "Test Page" in result.text
    assert "Some body text here" in result.text
    assert "来源: http://example.com" in result.text
    assert result.title == "Test Page"


@pytest.mark.asyncio
async def test_parse_crawl_link_discovery(parser, monkeypatch):
    def fake_playwright():
        class FakeBrowser:
            def __init__(self):
                self.call_count = 0
            async def new_page(self):
                self.call_count += 1
                idx = self.call_count
                class FakePage:
                    async def goto(self, *a, **k):
                        pass
                    async def title(self):
                        return f"Page {idx}"
                    async def evaluate(self, *a, **k):
                        return f"Body {idx}"
                    async def eval_on_selector_all(self, *a, **k):
                        if idx == 1:
                            return ["http://example.com/page2", "http://example.com/page3"]
                        return []
                    async def close(self):
                        pass
                return FakePage()
            async def close(self):
                pass

        class FakeP:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            @property
            def chromium(self):
                class FakeChromium:
                    async def launch(self, **k):
                        return FakeBrowser()
                return FakeChromium()

        return FakeP()

    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", fake_playwright
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", True
    )

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(source, max_depth=2, max_pages=10)
    assert isinstance(result, ParseResult)
    assert "Page 1" in result.text
    assert "Page 2" in result.text
    assert "Page 3" in result.text


@pytest.mark.asyncio
async def test_parse_crawl_same_domain_filter(parser, monkeypatch):
    def fake_playwright():
        class FakeBrowser:
            def __init__(self):
                self.call_count = 0
            async def new_page(self):
                self.call_count += 1
                idx = self.call_count
                class FakePage:
                    async def goto(self, *a, **k):
                        pass
                    async def title(self):
                        return f"Page {idx}"
                    async def evaluate(self, *a, **k):
                        return f"Body {idx}"
                    async def eval_on_selector_all(self, *a, **k):
                        if idx == 1:
                            return [
                                "http://example.com/allowed",
                                "http://other.com/blocked",
                            ]
                        return []
                    async def close(self):
                        pass
                return FakePage()
            async def close(self):
                pass

        class FakeP:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            @property
            def chromium(self):
                class FakeChromium:
                    async def launch(self, **k):
                        return FakeBrowser()
                return FakeChromium()

        return FakeP()

    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", fake_playwright
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", True
    )

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(
        source, max_depth=2, max_pages=10, same_domain_only=True
    )
    assert isinstance(result, ParseResult)
    assert "allowed" in result.text
    assert "other.com" not in result.text


@pytest.mark.asyncio
async def test_parse_crawl_cross_domain_allowed(parser, monkeypatch):
    def fake_playwright():
        class FakeBrowser:
            def __init__(self):
                self.call_count = 0
            async def new_page(self):
                self.call_count += 1
                idx = self.call_count
                class FakePage:
                    async def goto(self, *a, **k):
                        pass
                    async def title(self):
                        return f"Page {idx}"
                    async def evaluate(self, *a, **k):
                        return f"Body {idx}"
                    async def eval_on_selector_all(self, *a, **k):
                        if idx == 1:
                            return ["http://other.com/page"]
                        return []
                    async def close(self):
                        pass
                return FakePage()
            async def close(self):
                pass

        class FakeP:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            @property
            def chromium(self):
                class FakeChromium:
                    async def launch(self, **k):
                        return FakeBrowser()
                return FakeChromium()

        return FakeP()

    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", fake_playwright
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", True
    )

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(
        source, max_depth=2, max_pages=10, same_domain_only=False
    )
    assert isinstance(result, ParseResult)
    assert "other.com" in result.text


@pytest.mark.asyncio
async def test_parse_crawl_timeout_skips_page(parser, monkeypatch):
    def fake_playwright():
        class FakeBrowser:
            async def new_page(self):
                class FakePage:
                    async def goto(self, *a, **k):
                        raise Exception("Timeout")
                    async def close(self):
                        pass
                return FakePage()
            async def close(self):
                pass

        class FakeP:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            @property
            def chromium(self):
                class FakeChromium:
                    async def launch(self, **k):
                        return FakeBrowser()
                return FakeChromium()

        return FakeP()

    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", fake_playwright
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", True
    )

    async def mock_parse_link(source, **kwargs):
        return ParseResult(text="fallback", title="Fallback")

    monkeypatch.setattr(parser, "_parse_link", mock_parse_link)

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(source)
    assert result.text == "fallback"
    assert result.title == "Fallback"


@pytest.mark.asyncio
async def test_parse_crawl_non_http_links_filtered(parser, monkeypatch):
    def fake_playwright():
        class FakeBrowser:
            async def new_page(self):
                class FakePage:
                    async def goto(self, *a, **k):
                        pass
                    async def title(self):
                        return "Test"
                    async def evaluate(self, *a, **k):
                        return "Body"
                    async def eval_on_selector_all(self, *a, **k):
                        return ["ftp://example.com/file", "mailto:test@test.com", "javascript:void(0)"]
                    async def close(self):
                        pass
                return FakePage()
            async def close(self):
                pass

        class FakeP:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            @property
            def chromium(self):
                class FakeChromium:
                    async def launch(self, **k):
                        return FakeBrowser()
                return FakeChromium()

        return FakeP()

    monkeypatch.setattr(
        "service.core.parsers.web_parser.async_playwright", fake_playwright
    )
    monkeypatch.setattr(
        "service.core.parsers.web_parser.PLAYWRIGHT_AVAILABLE", True
    )

    source = FakeSource(url="http://example.com")
    result = await parser._parse_crawl(source, max_depth=2, max_pages=5)
    assert isinstance(result, ParseResult)
    assert result.title == "Test"
