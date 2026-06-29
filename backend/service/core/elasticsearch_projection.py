from __future__ import annotations

from dataclasses import dataclass
import json
from json import JSONDecodeError
from typing import Any, Iterable

import httpx

from service.config import get_settings
from service.models import SourceChunk


class ElasticsearchProjectionError(RuntimeError):
    pass


class ElasticsearchHttpClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        settings = get_settings()
        self._client = httpx.Client(
            base_url=(base_url or settings.elasticsearch_url).rstrip("/"),
            timeout=timeout_seconds or settings.service_health_timeout_seconds,
            transport=transport,
        )

    def request(self, method: str, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        method = method.upper()
        try:
            response = self._client.request(method, path, json=json)
        except httpx.RequestError as exc:
            raise ElasticsearchProjectionError(
                f"Elasticsearch request failed: {method} {path} could not connect"
            ) from exc
        if response.status_code >= 400:
            body = _response_json_or_none(response)
            if _is_existing_index_response(body):
                return body
            raise ElasticsearchProjectionError(
                f"Elasticsearch request failed: {method} {path} returned status {response.status_code}"
            )
        if not response.content:
            return {}
        body = _response_json_or_none(response)
        if body is None:
            raise ElasticsearchProjectionError(f"Elasticsearch request failed: {method} {path} returned invalid JSON")
        return body


@dataclass(frozen=True)
class SourceChunkDocument:
    chunk_id: int
    source_id: int
    user_id: int | None
    knowledge_base_id: int | None
    source_title: str
    text: str
    embedding: list[float]

    @classmethod
    def from_chunk(cls, chunk: SourceChunk) -> "SourceChunkDocument":
        try:
            embedding = json.loads(chunk.embedding_json)
        except (JSONDecodeError, TypeError) as exc:
            raise ElasticsearchProjectionError(f"chunk {chunk.id} embedding_json must contain a JSON array") from exc
        if not isinstance(embedding, list):
            raise ElasticsearchProjectionError(f"chunk {chunk.id} embedding_json must contain a JSON array")
        try:
            parsed_embedding = [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise ElasticsearchProjectionError(f"chunk {chunk.id} embedding_json must contain numeric values") from exc
        source = chunk.source
        if source is None or not getattr(source, "title", None):
            raise ElasticsearchProjectionError(f"chunk {chunk.id} must have loaded source metadata")
        return cls(
            chunk_id=chunk.id,
            source_id=chunk.source_id,
            user_id=chunk.user_id,
            knowledge_base_id=chunk.knowledge_base_id,
            source_title=source.title,
            text=chunk.text,
            embedding=parsed_embedding,
        )

    def to_elasticsearch(self) -> dict[str, Any]:
        return {
            "chunk_id": _keyword(self.chunk_id),
            "source_id": _keyword(self.source_id),
            "user_id": _keyword(self.user_id),
            "knowledge_base_id": _keyword(self.knowledge_base_id),
            "source_title": self.source_title,
            "text": self.text,
            "embedding": self.embedding,
        }


class ElasticsearchProjection:
    def __init__(
        self,
        client: ElasticsearchHttpClient | None = None,
        index_name: str | None = None,
        embedding_dimensions: int | None = None,
    ):
        settings = get_settings()
        self.client = client or ElasticsearchHttpClient()
        self.index_name = index_name or settings.elasticsearch_index
        self.embedding_dimensions = embedding_dimensions or settings.embedding_dimensions

    def ensure_index(self) -> dict[str, Any]:
        response = self.client.request("PUT", f"/{self.index_name}", json=self._mapping_body())
        if _is_existing_index_response(response):
            return {"acknowledged": True, "already_exists": True}
        return response

    def index_chunk(self, document: SourceChunkDocument) -> dict[str, Any]:
        return self.client.request(
            "PUT",
            f"/{self.index_name}/_doc/source_chunk:{document.chunk_id}",
            json=document.to_elasticsearch(),
        )

    def delete_source(self, user_id: int | None, knowledge_base_id: int | None, source_id: int) -> dict[str, Any]:
        return self.client.request(
            "POST",
            f"/{self.index_name}/_delete_by_query",
            json={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"user_id": _keyword(user_id)}},
                            {"term": {"knowledge_base_id": _keyword(knowledge_base_id)}},
                            {"term": {"source_id": _keyword(source_id)}},
                        ]
                    }
                }
            },
        )

    def search_bm25(
        self,
        query: str,
        user_id: int | None,
        knowledge_base_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        response = self.client.request(
            "POST",
            f"/{self.index_name}/_search",
            json={
                "size": limit,
                "query": {
                    "bool": {
                        "filter": self._scope_filter(user_id, knowledge_base_id),
                        "must": {
                            "multi_match": {
                                "query": query,
                                "fields": ["source_title^2", "text"],
                            }
                        },
                    }
                },
            },
        )
        return _hits(response)

    def search_vector(
        self,
        vector: list[float],
        user_id: int | None,
        knowledge_base_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        response = self.client.request(
            "POST",
            f"/{self.index_name}/_search",
            json={
                "size": limit,
                "knn": {
                    "field": "embedding",
                    "query_vector": vector,
                    "k": limit,
                    "num_candidates": max(limit * 5, 50),
                    "filter": self._scope_filter(user_id, knowledge_base_id),
                },
            },
        )
        return _hits(response)

    def _mapping_body(self) -> dict[str, Any]:
        return {
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "source_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "knowledge_base_id": {"type": "keyword"},
                    "source_title": {"type": "text"},
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self.embedding_dimensions,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            }
        }

    def _scope_filter(self, user_id: int | None, knowledge_base_id: int | None) -> list[dict[str, Any]]:
        return [
            {"term": {"user_id": _keyword(user_id)}},
            {"term": {"knowledge_base_id": _keyword(knowledge_base_id)}},
        ]


def rebuild_source_chunks(chunks: Iterable[SourceChunk], projection: ElasticsearchProjection) -> int:
    projection.ensure_index()
    indexed_count = 0
    for chunk in chunks:
        if chunk.embedding_status != "embedded" or not chunk.embedding_json:
            continue
        projection.index_chunk(SourceChunkDocument.from_chunk(chunk))
        indexed_count += 1
    return indexed_count


def _hits(response: dict[str, Any]) -> list[dict[str, Any]]:
    hits = response.get("hits", {}).get("hits", [])
    if not isinstance(hits, list):
        return []
    return hits


def _keyword(value: int | str | None) -> str:
    return "" if value is None else str(value)


def _response_json_or_none(response: httpx.Response) -> dict[str, Any] | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _is_existing_index_response(response: dict[str, Any] | None) -> bool:
    if not response:
        return False
    error = response.get("error")
    return isinstance(error, dict) and error.get("type") == "resource_already_exists_exception"
