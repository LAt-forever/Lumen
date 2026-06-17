from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from service.config import get_settings
from service.core.knowledge import KnowledgeService
from service.core.llm import HttpxChatCompletionClient
from service.core.parsers import get_parser
from service.core.storage import move_to_final, resolve_file_path, save_temp_upload
from service.models import Source
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate, WebCrawlRequest

TYPE_MAP: dict[str, str] = {
    ".txt": "text",
    ".md": "markdown",
    ".pdf": "pdf",
    ".docx": "docx",
    ".epub": "epub",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
}


def source_type_for_filename(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    return TYPE_MAP.get(suffix)


def decode_text_upload(file_data: bytes) -> str:
    try:
        return file_data.decode("utf-8").strip()
    except UnicodeDecodeError:
        for encoding in ("gbk", "gb2312", "big5"):
            try:
                return file_data.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
    return file_data.decode("utf-8", errors="replace").strip()


@lru_cache
def build_vision_client() -> HttpxChatCompletionClient | None:
    settings = get_settings()
    if settings.llm_api_key and settings.llm_model:
        return HttpxChatCompletionClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return None


def parser_kwargs_for_source(source_type: str) -> dict[str, Any]:
    if source_type != "image":
        return {}
    vision_client = build_vision_client()
    if vision_client is None:
        return {}
    return {"vision_client": vision_client}


def parse_payload(payload_json: str) -> dict[str, Any]:
    if not payload_json:
        return {}
    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        raise ValueError("Ingestion payload must be a JSON object")
    return payload


class IngestionService:
    def __init__(self, sources: SourceRepository, chunks: ChunkRepository):
        self.sources = sources
        self.chunks = chunks
        self.knowledge = KnowledgeService(sources, chunks)

    async def create_and_index_upload(self, filename: str, file_data: bytes) -> Source:
        source_type = source_type_for_filename(filename)
        if source_type is None:
            source = self.sources.create(SourceCreate(title=filename, source_type="text", filename=filename))
            self.sources.mark_failed(source.id, "Unsupported file type")
            return self._source(source.id)

        if source_type in ("text", "markdown"):
            content = decode_text_upload(file_data)
            source = self.sources.create(
                SourceCreate(title=filename, source_type=source_type, filename=filename, content=content)
            )
            await self.parse_existing_source(source.id)
            return self.index_existing_source(source.id)

        temp_relative: str | None = None
        source_id: int | None = None
        try:
            temp_relative = save_temp_upload(file_data, filename)
            source = self.sources.create(SourceCreate(title=filename, source_type=source_type, filename=temp_relative))
            source_id = source.id
            final_relative = move_to_final(temp_relative, source.id, filename)
            temp_relative = None
            self.sources.update_filename(source.id, final_relative)
            await self.parse_existing_source(source.id)
            return self.index_existing_source(source.id)
        except Exception:
            if temp_relative is not None:
                resolve_file_path(temp_relative).unlink(missing_ok=True)
            if source_id is not None:
                self.sources.mark_failed(source_id, "Could not parse file")
            raise

    async def parse_existing_source(self, source_id: int) -> Source:
        source = self._source(source_id)
        parser = get_parser(source.source_type)
        result = await parser.parse(source, **parser_kwargs_for_source(source.source_type))
        return self._store_parse_result(source.id, result.text, result.title)

    async def parse_link_source(self, source_id: int) -> Source:
        source = self._source(source_id)
        parser = get_parser("link")
        result = await parser.parse(source)
        return self._store_parse_result(source.id, result.text)

    async def parse_crawl_source(self, source_id: int, request: WebCrawlRequest) -> Source:
        source = self._source(source_id)
        parser = get_parser("web_crawl")
        result = await parser.parse(
            source,
            mode="crawl",
            max_depth=request.max_depth,
            max_pages=request.max_pages,
            same_domain_only=request.same_domain_only,
        )
        return self._store_parse_result(source.id, result.text, result.title)

    async def parse_bookmark_source(self, source_id: int) -> Source:
        try:
            return await self.parse_link_source(source_id)
        except Exception:
            source = self._source(source_id)
            fallback_content = f"标题: {source.title}\n链接: {source.url}"
            self.sources.update_content(source.id, fallback_content)
            return self._source(source.id)

    def index_existing_source(self, source_id: int) -> Source:
        self.knowledge.index_source(source_id)
        return self._source(source_id)

    async def retry_source(self, source_id: int) -> Source:
        source = self._source(source_id)
        if source.source_type == "link":
            await self.parse_link_source(source.id)
        elif source.source_type == "bookmark":
            await self.parse_bookmark_source(source.id)
        elif source.source_type == "web_crawl":
            request = WebCrawlRequest(url=source.url or source.title)
            await self.parse_crawl_source(source.id, request)
        else:
            await self.parse_existing_source(source.id)
        return self.index_existing_source(source.id)

    def _store_parse_result(self, source_id: int, text: str, title: str | None = None) -> Source:
        content = text.strip()
        if not content:
            raise ValueError("No text content found")
        self.sources.update_content(source_id, content)
        if title:
            self.sources.update_title(source_id, title)
        return self._source(source_id)

    def _source(self, source_id: int) -> Source:
        source = self.sources.get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        return source
