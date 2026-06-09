import io
from pathlib import Path

import pytest

from service.core.parsers.base import ParseResult
from service.core.parsers.image_parser import ImageParser


class FakeSource:
    def __init__(self, content=None, url=None, filename=None, title="", source_type=""):
        self.content = content
        self.url = url
        self.filename = filename
        self.title = title
        self.source_type = source_type


class MockVisionClient:
    def __init__(self, response: str = "这是一张测试图片。"):
        self.response = response
        self.last_messages = None

    def complete(self, messages: list[dict]) -> str:
        self.last_messages = messages
        return self.response


@pytest.fixture
def parser():
    return ImageParser()


def test_supported_types(parser):
    assert parser.supported_types == frozenset({"image"})


@pytest.mark.asyncio
async def test_parse_missing_filename_raises(parser):
    source = FakeSource(filename=None)
    with pytest.raises(ValueError, match="missing filename"):
        await parser.parse(source)


@pytest.mark.asyncio
async def test_parse_vision_only_no_ocr_deps(parser, tmp_path: Path, monkeypatch):
    """Test that vision description is used when OCR deps are unavailable."""
    from service.core import parsers
    from service.core.parsers import image_parser as ip_mod

    monkeypatch.setattr(ip_mod, "pytesseract", None)
    monkeypatch.setattr(ip_mod, "Image", None)

    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    # Create a tiny valid PNG (1x1 pixel)
    import struct
    import zlib
    png_data = _make_minimal_png()
    img_path = tmp_path / "test.png"
    img_path.write_bytes(png_data)

    vision_client = MockVisionClient("图片里有一只猫。")
    source = FakeSource(filename="test.png")
    result = await parser.parse(source, vision_client=vision_client)
    assert isinstance(result, ParseResult)
    assert "[图片内容描述]" in result.text
    assert "图片里有一只猫。" in result.text
    assert result.metadata["vision_success"] is True
    assert result.metadata["ocr_success"] is False


@pytest.mark.asyncio
async def test_parse_both_fail_raises(parser, tmp_path: Path, monkeypatch):
    """Test that ValueError is raised when both OCR and vision fail."""
    from service.core import parsers
    from service.core.parsers import image_parser as ip_mod

    monkeypatch.setattr(ip_mod, "pytesseract", None)
    monkeypatch.setattr(ip_mod, "Image", None)

    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    png_data = _make_minimal_png()
    img_path = tmp_path / "test.png"
    img_path.write_bytes(png_data)

    # Vision client that raises
    class BrokenVisionClient:
        def complete(self, messages):
            raise RuntimeError("vision failed")

    source = FakeSource(filename="test.png")
    with pytest.raises(ValueError, match="no recognizable text"):
        await parser.parse(source, vision_client=BrokenVisionClient())


@pytest.mark.asyncio
async def test_parse_vision_failure_non_fatal(parser, tmp_path: Path, monkeypatch):
    """Test that vision failure is non-fatal when OCR succeeds."""
    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    # Create a simple image with text-like content using PIL if available
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        pytest.skip("PIL not available")

    img = Image.new("RGB", (200, 50), color="white")
    draw = ImageDraw.Draw(img)
    # Use default font
    draw.text((10, 10), "Hello Image", fill="black")
    img_path = tmp_path / "test_hello.png"
    img.save(img_path)

    # Mock pytesseract to return text
    from service.core.parsers import image_parser as ip_mod

    class FakeTesseract:
        @staticmethod
        def image_to_string(img, lang=None):
            return "Hello Image"

    monkeypatch.setattr(ip_mod, "pytesseract", FakeTesseract())

    # Vision client that fails
    class BrokenVisionClient:
        def complete(self, messages):
            raise RuntimeError("vision failed")

    source = FakeSource(filename="test_hello.png")
    result = await parser.parse(source, vision_client=BrokenVisionClient())
    assert isinstance(result, ParseResult)
    assert "Hello Image" in result.text
    assert result.metadata["ocr_success"] is True
    assert result.metadata["vision_success"] is False


@pytest.mark.asyncio
async def test_parse_merge_format_both_succeed(parser, tmp_path: Path, monkeypatch):
    """Test the merged format when both OCR and vision succeed."""
    from service.core import storage
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)

    try:
        from PIL import Image, ImageDraw
    except Exception:
        pytest.skip("PIL not available")

    img = Image.new("RGB", (200, 50), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Hello Image", fill="black")
    img_path = tmp_path / "test_merge.png"
    img.save(img_path)

    from service.core.parsers import image_parser as ip_mod

    class FakeTesseract:
        @staticmethod
        def image_to_string(img, lang=None):
            return "Hello Image"

    monkeypatch.setattr(ip_mod, "pytesseract", FakeTesseract())

    vision_client = MockVisionClient("这是一张写着Hello Image的图片。")
    source = FakeSource(filename="test_merge.png")
    result = await parser.parse(source, vision_client=vision_client)
    assert isinstance(result, ParseResult)
    assert "[图片文字识别]" in result.text
    assert "Hello Image" in result.text
    assert "[图片内容描述]" in result.text
    assert "这是一张写着Hello Image的图片。" in result.text
    assert result.metadata["ocr_success"] is True
    assert result.metadata["vision_success"] is True

    # Verify vision message format
    messages = vision_client.last_messages
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def _make_minimal_png() -> bytes:
    """Create a minimal valid 1x1 PNG file in memory."""
    import struct
    import zlib

    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR: 1x1, 8-bit RGB
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)

    # IDAT: compressed image data (filter byte 0 + RGB pixel)
    raw = b"\x00\xff\x00\x00"  # filter + red pixel
    compressed = zlib.compress(raw)
    idat = _png_chunk(b"IDAT", compressed)

    # IEND
    iend = _png_chunk(b"IEND", b"")

    return sig + ihdr + idat + iend
