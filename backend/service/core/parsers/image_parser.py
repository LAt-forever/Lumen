import asyncio
import base64
import mimetypes
from pathlib import Path

from service.core.llm import ChatCompletionError
from service.core.parsers import register_parser
from service.core.parsers.base import ParseResult
from service.core.storage import resolve_file_path
from service.models import Source

# Optional OCR dependencies — gracefully degrade if missing
try:
    import pytesseract
    from PIL import Image
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]


class ImageParser:
    supported_types = frozenset({"image"})

    def __init__(self, vision_client=None):
        self.vision_client = vision_client

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        if not source.filename:
            raise ValueError("Image source is missing filename")

        file_path = resolve_file_path(source.filename)

        # Phase 1: OCR with pytesseract (CPU-intensive, run in thread)
        ocr_text = ""
        if pytesseract is not None and Image is not None:
            try:

                def _do_ocr(path: Path) -> str:
                    with Image.open(path) as img:
                        if img.mode not in ("RGB", "L"):
                            img = img.convert("RGB")
                        return pytesseract.image_to_string(img, lang="chi_sim+eng").strip()

                ocr_text = await asyncio.to_thread(_do_ocr, file_path)
            except Exception:
                pass  # OCR failure is non-fatal

        # Phase 2: Vision description (optional, non-fatal)
        vision_desc = ""
        vision_client = kwargs.get("vision_client") or self.vision_client
        if vision_client is not None:
            try:
                mime_type, _ = mimetypes.guess_type(str(file_path))
                mime_type = mime_type or "image/png"
                with open(file_path, "rb") as f:
                    image_bytes = f.read()
                b64_data = base64.b64encode(image_bytes).decode("utf-8")
                data_url = f"data:{mime_type};base64,{b64_data}"

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请详细描述这张图片的内容。如果图片包含文字，请同时概括文字的主要信息。用中文回答。",
                            },
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ]
                vision_desc = await asyncio.to_thread(vision_client.complete, messages)
                vision_desc = vision_desc.strip()
            except (ChatCompletionError, Exception):
                pass  # Vision failure is non-fatal

        # Build result
        metadata: dict[str, str | bool] = {
            "filename": source.filename,
            "ocr_available": pytesseract is not None and Image is not None,
            "ocr_success": bool(ocr_text),
            "vision_success": bool(vision_desc),
        }

        if ocr_text and vision_desc:
            merged = f"[图片文字识别]\n{ocr_text}\n\n[图片内容描述]\n{vision_desc}"
            return ParseResult(text=merged, metadata=metadata)

        if ocr_text:
            return ParseResult(text=ocr_text, metadata=metadata)

        if vision_desc:
            merged = f"[图片内容描述]\n{vision_desc}"
            return ParseResult(text=merged, metadata=metadata)

        raise ValueError(
            "Image contains no recognizable text and vision description failed"
        )


register_parser(ImageParser())
