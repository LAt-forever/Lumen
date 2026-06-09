from fastapi.testclient import TestClient
from service.main import app

client = TestClient(app)


class TestSourcesAPIExtended:
    def test_upload_unsupported_file_type(self):
        response = client.post(
            "/api/sources/upload",
            files={"files": ("test.xyz", b"content", "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["failed"] >= 1

    def test_crawl_invalid_url(self):
        response = client.post(
            "/api/sources/crawl",
            json={"url": "not-a-url", "max_depth": 1, "max_pages": 5},
        )
        assert response.status_code == 200

    def test_bookmark_import_empty_html(self):
        response = client.post(
            "/api/sources/bookmarks",
            json={"html_content": "<html></html>"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "No bookmarks found" in data["detail"]
