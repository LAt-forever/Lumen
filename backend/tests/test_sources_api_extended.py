class TestSourcesAPIExtended:
    def test_upload_unsupported_file_type(self, client):
        response = client.post(
            "/api/sources/upload",
            files={"files": ("test.xyz", b"content", "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["failed"] >= 1

    def test_crawl_invalid_url(self, client):
        response = client.post(
            "/api/sources/crawl",
            json={"url": "not-a-url", "max_depth": 1, "max_pages": 5},
        )
        assert response.status_code == 200

    def test_bookmark_import_empty_html(self, client):
        response = client.post(
            "/api/sources/bookmarks",
            json={"html_content": "<html></html>"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "No bookmarks found" in data["detail"]

    def test_upload_multiple_files(self, client):
        response = client.post(
            "/api/sources/upload",
            files=[
                ("files", ("a.txt", b"First file content", "text/plain")),
                ("files", ("b.txt", b"Second file content", "text/plain")),
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["sources"]) == 2
        types = {s["source_type"] for s in data["sources"]}
        assert types == {"text"}

    def test_upload_gbk_encoded_file(self, client):
        """GBK-encoded Chinese text should be decoded correctly with fallback."""
        gbk_bytes = "这是一个GBK编码的测试文件。".encode("gbk")
        response = client.post(
            "/api/sources/upload",
            files=[("files", ("gbk.txt", gbk_bytes, "text/plain"))],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["succeeded"] == 1
        source = data["sources"][0]
        assert source["status"] == "indexed"

        # Verify content was indexed and searchable
        search = client.get("/api/search", params={"q": "GBK编码"})
        assert search.status_code == 200
        results = search.json()
        assert any("gbk.txt" == r["source_title"] for r in results)

    def test_bookmark_import_success(self, client, monkeypatch):
        from service.core.parsers.web_parser import WebParser

        async def fake_parse_link(self, source, **kwargs):
            from service.core.parsers.base import ParseResult

            return ParseResult(
                text=f"Content from {source.url}",
                title="Mock Page",
            )

        monkeypatch.setattr(WebParser, "_parse_link", fake_parse_link)

        html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
        <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
        <TITLE>Bookmarks</TITLE>
        <H1>Bookmarks</H1>
        <DL><p>
            <DT><A HREF="https://example.com/1">First Bookmark</A>
            <DT><A HREF="https://example.com/2">Second Bookmark</A>
        </DL><p>"""

        response = client.post(
            "/api/sources/bookmarks",
            json={"html_content": html},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["sources"]) == 2
        for source in data["sources"]:
            assert source["source_type"] == "bookmark"
            assert source["status"] == "indexed"
