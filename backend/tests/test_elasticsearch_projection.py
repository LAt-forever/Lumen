from types import SimpleNamespace

import httpx
import pytest

from service.core.elasticsearch_projection import (
    ElasticsearchHttpClient,
    ElasticsearchProjection,
    ElasticsearchProjectionError,
    SourceChunkDocument,
    rebuild_source_chunks,
)


class FakeElasticsearchClient:
    def __init__(self):
        self.requests = []
        self.responses = []

    def request(self, method, path, json=None):
        self.requests.append({"method": method, "path": path, "json": json})
        if self.responses:
            return self.responses.pop(0)
        return {"acknowledged": True}


def test_ensure_index_creates_mapping_with_dense_vector_dims():
    client = FakeElasticsearchClient()
    projection = ElasticsearchProjection(client=client, index_name="chunks", embedding_dimensions=3)

    projection.ensure_index()

    assert client.requests == [
        {
            "method": "PUT",
            "path": "/chunks",
            "json": {
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "source_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "knowledge_base_id": {"type": "keyword"},
                        "source_title": {"type": "text"},
                        "text": {"type": "text"},
                        "embedding": {"type": "dense_vector", "dims": 3, "index": True, "similarity": "cosine"},
                    }
                }
            },
        }
    ]


def test_ensure_index_tolerates_existing_index_response():
    client = FakeElasticsearchClient()
    client.responses.append(
        {
            "error": {
                "type": "resource_already_exists_exception",
                "reason": "index [chunks] already exists",
            },
            "status": 400,
        }
    )
    projection = ElasticsearchProjection(client=client, index_name="chunks", embedding_dimensions=3)

    assert projection.ensure_index() == {"acknowledged": True, "already_exists": True}
    assert client.requests[0]["method"] == "PUT"
    assert client.requests[0]["path"] == "/chunks"


def test_index_chunk_writes_scoped_document_with_embedding():
    client = FakeElasticsearchClient()
    projection = ElasticsearchProjection(client=client, index_name="chunks", embedding_dimensions=3)
    document = SourceChunkDocument(
        chunk_id=42,
        source_id=7,
        user_id=11,
        knowledge_base_id=13,
        source_title="Comet Notes",
        text="Projection text",
        embedding=[0.1, 0.2, 0.3],
    )

    projection.index_chunk(document)

    assert client.requests == [
        {
            "method": "PUT",
            "path": "/chunks/_doc/source_chunk:42",
            "json": {
                "chunk_id": "42",
                "source_id": "7",
                "user_id": "11",
                "knowledge_base_id": "13",
                "source_title": "Comet Notes",
                "text": "Projection text",
                "embedding": [0.1, 0.2, 0.3],
            },
        }
    ]


def test_delete_source_deletes_only_matching_scope_and_source():
    client = FakeElasticsearchClient()
    projection = ElasticsearchProjection(client=client, index_name="chunks", embedding_dimensions=3)

    projection.delete_source(user_id=11, knowledge_base_id=13, source_id=7)

    assert client.requests == [
        {
            "method": "POST",
            "path": "/chunks/_delete_by_query",
            "json": {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"user_id": "11"}},
                            {"term": {"knowledge_base_id": "13"}},
                            {"term": {"source_id": "7"}},
                        ]
                    }
                }
            },
        }
    ]


def test_search_bm25_uses_scoped_filters_and_multi_match():
    client = FakeElasticsearchClient()
    client.responses.append({"hits": {"hits": [{"_id": "source_chunk:42"}]}})
    projection = ElasticsearchProjection(client=client, index_name="chunks", embedding_dimensions=3)

    hits = projection.search_bm25("projection query", user_id=11, knowledge_base_id=13, limit=4)

    assert hits == [{"_id": "source_chunk:42"}]
    assert client.requests == [
        {
            "method": "POST",
            "path": "/chunks/_search",
            "json": {
                "size": 4,
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"user_id": "11"}},
                            {"term": {"knowledge_base_id": "13"}},
                        ],
                        "must": {
                            "multi_match": {
                                "query": "projection query",
                                "fields": ["source_title^2", "text"],
                            }
                        },
                    }
                },
            },
        }
    ]


def test_search_vector_uses_es8_knn_with_scoped_filters():
    client = FakeElasticsearchClient()
    client.responses.append({"hits": {"hits": [{"_id": "source_chunk:42"}]}})
    projection = ElasticsearchProjection(client=client, index_name="chunks", embedding_dimensions=3)

    hits = projection.search_vector([0.1, 0.2, 0.3], user_id=11, knowledge_base_id=13, limit=4)

    assert hits == [{"_id": "source_chunk:42"}]
    assert client.requests == [
        {
            "method": "POST",
            "path": "/chunks/_search",
            "json": {
                "size": 4,
                "knn": {
                    "field": "embedding",
                    "query_vector": [0.1, 0.2, 0.3],
                    "k": 4,
                    "num_candidates": 50,
                    "filter": [
                        {"term": {"user_id": "11"}},
                        {"term": {"knowledge_base_id": "13"}},
                    ],
                },
            },
        }
    ]


def test_rebuild_source_chunks_indexes_only_embedded_chunks_with_embeddings():
    client = FakeElasticsearchClient()
    projection = ElasticsearchProjection(client=client, index_name="chunks", embedding_dimensions=3)
    source = SimpleNamespace(id=7, title="Loaded Source")
    chunks = [
        SimpleNamespace(
            id=1,
            source_id=7,
            source=source,
            user_id=11,
            knowledge_base_id=13,
            text="Indexed text",
            embedding_status="embedded",
            embedding_json="[0.1, 0.2, 0.3]",
        ),
        SimpleNamespace(
            id=2,
            source_id=7,
            source=source,
            user_id=11,
            knowledge_base_id=13,
            text="Skipped pending",
            embedding_status="pending",
            embedding_json="[0.4, 0.5, 0.6]",
        ),
        SimpleNamespace(
            id=3,
            source_id=7,
            source=source,
            user_id=11,
            knowledge_base_id=13,
            text="Skipped blank",
            embedding_status="embedded",
            embedding_json="",
        ),
    ]

    count = rebuild_source_chunks(chunks, projection)

    assert count == 1
    assert [request["path"] for request in client.requests] == ["/chunks", "/chunks/_doc/source_chunk:1"]
    assert client.requests[1]["json"]["source_title"] == "Loaded Source"
    assert client.requests[1]["json"]["embedding"] == [0.1, 0.2, 0.3]


def test_http_client_wraps_invalid_json_response():
    def handler(request):
        return httpx.Response(200, content=b"not-json", request=request)

    client = ElasticsearchHttpClient(base_url="https://user:secret@example.test", transport=httpx.MockTransport(handler))

    with pytest.raises(ElasticsearchProjectionError) as exc_info:
        client.request("GET", "/chunks")

    message = str(exc_info.value)
    assert "GET /chunks returned invalid JSON" in message
    assert "secret" not in message
    assert "example.test" not in message


def test_http_client_uses_sanitized_non_2xx_errors():
    def handler(request):
        return httpx.Response(503, json={"error": "https://user:secret@example.test leaked"}, request=request)

    client = ElasticsearchHttpClient(base_url="https://user:secret@example.test", transport=httpx.MockTransport(handler))

    with pytest.raises(ElasticsearchProjectionError) as exc_info:
        client.request("PUT", "/chunks")

    message = str(exc_info.value)
    assert message == "Elasticsearch request failed: PUT /chunks returned status 503"
    assert "secret" not in message
    assert "example.test" not in message


@pytest.mark.parametrize("embedding_json", ["not-json", '{"x": 1}', '["not-a-number"]'])
def test_source_chunk_document_wraps_malformed_embeddings(embedding_json):
    chunk = SimpleNamespace(
        id=1,
        source_id=7,
        source=SimpleNamespace(title="Loaded Source"),
        user_id=11,
        knowledge_base_id=13,
        text="Bad embedding",
        embedding_json=embedding_json,
    )

    with pytest.raises(ElasticsearchProjectionError):
        SourceChunkDocument.from_chunk(chunk)


def test_source_chunk_document_requires_loaded_source_metadata():
    chunk = SimpleNamespace(
        id=1,
        source_id=7,
        source=None,
        user_id=11,
        knowledge_base_id=13,
        text="Missing source",
        embedding_json="[0.1, 0.2, 0.3]",
    )

    with pytest.raises(ElasticsearchProjectionError):
        SourceChunkDocument.from_chunk(chunk)
