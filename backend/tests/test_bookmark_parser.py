import pytest

from service.core.parsers.bookmark_parser import BookmarkParser


class FakeSource:
    def __init__(self, content=None, url=None, filename=None, title="", source_type=""):
        self.content = content
        self.url = url
        self.filename = filename
        self.title = title
        self.source_type = source_type


@pytest.fixture
def parser():
    return BookmarkParser()


def test_supported_types(parser):
    assert parser.supported_types == frozenset({"bookmark"})


@pytest.mark.asyncio
async def test_empty_content_raises_value_error(parser):
    source = FakeSource(content="")
    with pytest.raises(ValueError, match="No bookmarks found"):
        await parser.parse(source)


@pytest.mark.asyncio
async def test_no_bookmarks_raises_value_error(parser):
    source = FakeSource(content="<html><body><p>No bookmarks here</p></body></html>")
    with pytest.raises(ValueError, match="No bookmarks found"):
        await parser.parse(source)


@pytest.mark.asyncio
async def test_valid_bookmarks_without_description(parser):
    html = """<!DOCTYPE netscape-bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://example.com">Example</A>
    <DT><A HREF="https://test.com">Test Site</A>
</DL><p>
"""
    source = FakeSource(content=html)
    result = await parser.parse(source)

    assert "标题: Example" in result.text
    assert "链接: https://example.com" in result.text
    assert "标题: Test Site" in result.text
    assert "链接: https://test.com" in result.text
    assert result.metadata == {"bookmark_count": 2}
    assert "---" in result.text


@pytest.mark.asyncio
async def test_valid_bookmarks_with_description(parser):
    html = """<!DOCTYPE netscape-bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://example.com">Example</A>
    <DD>This is the example description
    <DT><A HREF="https://test.com">Test Site</A>
    <DD>Another description here
</DL><p>
"""
    source = FakeSource(content=html)
    result = await parser.parse(source)

    assert "标题: Example" in result.text
    assert "链接: https://example.com" in result.text
    assert "描述: This is the example description" in result.text
    assert "标题: Test Site" in result.text
    assert "描述: Another description here" in result.text
    assert result.metadata == {"bookmark_count": 2}


@pytest.mark.asyncio
async def test_mixed_bookmarks_with_and_without_description(parser):
    html = """<!DOCTYPE netscape-bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://with-desc.com">With Description</A>
    <DD>This has a description
    <DT><A HREF="https://no-desc.com">No Description</A>
</DL><p>
"""
    source = FakeSource(content=html)
    result = await parser.parse(source)

    assert "标题: With Description" in result.text
    assert "描述: This has a description" in result.text
    assert "标题: No Description" in result.text
    # Make sure "描述" doesn't appear for the second bookmark
    parts = result.text.split("\n\n---\n\n")
    assert len(parts) == 2
    assert "描述:" in parts[0]  # First bookmark has description
    assert "描述:" not in parts[1]  # Second bookmark has no description
    assert result.metadata == {"bookmark_count": 2}


@pytest.mark.asyncio
async def test_bookmarks_in_nested_dl(parser):
    html = """<!DOCTYPE netscape-bookmark-file-1>
<TITLE>Bookmarks</TITLE>
<DL><p>
    <DT><H3>Folder</H3>
    <DL><p>
        <DT><A HREF="https://nested.com">Nested Bookmark</A>
        <DD>Nested description
    </DL><p>
    <DT><A HREF="https://top.com">Top Level</A>
</DL><p>
"""
    source = FakeSource(content=html)
    result = await parser.parse(source)

    assert "标题: Nested Bookmark" in result.text
    assert "链接: https://nested.com" in result.text
    assert "描述: Nested description" in result.text
    assert "标题: Top Level" in result.text
    assert "链接: https://top.com" in result.text
    assert result.metadata == {"bookmark_count": 2}


@pytest.mark.asyncio
async def test_skips_dt_without_a_tag(parser):
    html = """<!DOCTYPE netscape-bookmark-file-1>
<TITLE>Bookmarks</TITLE>
<DL><p>
    <DT><H3>Just a folder</H3>
    <DT><A HREF="https://only-link.com">Only Link</A>
</DL><p>
"""
    source = FakeSource(content=html)
    result = await parser.parse(source)

    assert "Only Link" in result.text
    assert "Just a folder" not in result.text
    assert result.metadata == {"bookmark_count": 1}


@pytest.mark.asyncio
async def test_skips_empty_href_or_title(parser):
    html = """<!DOCTYPE netscape-bookmark-file-1>
<TITLE>Bookmarks</TITLE>
<DL><p>
    <DT><A HREF="">Empty Href</A>
    <DT><A HREF="https://valid.com">Valid</A>
    <DT><A HREF="https://empty-title.com"></A>
</DL><p>
"""
    source = FakeSource(content=html)
    result = await parser.parse(source)

    assert "Valid" in result.text
    assert "Empty Href" not in result.text
    assert "empty-title" not in result.text
    assert result.metadata == {"bookmark_count": 1}
