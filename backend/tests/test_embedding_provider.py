import pytest

from service.config import Settings
from service.core.embeddings import (
    EmbeddingProviderConfig,
    HashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
)
from service.models import LLMProviderProfile


def test_openai_compatible_embedding_provider_batches_and_posts_payload(monkeypatch):
    requests = []

    class FakeResponse:
        def __init__(self, embeddings):
            self.embeddings = embeddings

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": embedding} for embedding in self.embeddings]}

    def fake_post(url, headers, json, timeout):
        requests.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        embeddings_by_text = {
            "alpha": [1.0, 0.0, 0.0],
            "beta": [0.0, 1.0, 0.0],
            "gamma": [0.0, 0.0, 1.0],
            "delta": [0.5, 0.5, 0.0],
        }
        return FakeResponse([embeddings_by_text[text] for text in json["input"]])

    monkeypatch.setattr("service.core.embeddings.httpx.post", fake_post)
    provider = OpenAICompatibleEmbeddingProvider(
        EmbeddingProviderConfig(
            base_url="https://provider.example/v1/",
            model="text-embedding-test",
            api_key="embedding-secret",
            dimensions=3,
            batch_size=2,
            timeout_seconds=7,
        )
    )

    embeddings = provider.embed_many(["alpha", "beta", "gamma", "delta"])

    assert embeddings == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.5, 0.5, 0.0],
    ]
    assert requests == [
        {
            "url": "https://provider.example/v1/embeddings",
            "headers": {
                "Authorization": "Bearer embedding-secret",
                "Content-Type": "application/json",
            },
            "json": {"model": "text-embedding-test", "input": ["alpha", "beta"]},
            "timeout": 7,
        },
        {
            "url": "https://provider.example/v1/embeddings",
            "headers": {
                "Authorization": "Bearer embedding-secret",
                "Content-Type": "application/json",
            },
            "json": {"model": "text-embedding-test", "input": ["gamma", "delta"]},
            "timeout": 7,
        },
    ]


def test_openai_compatible_embedding_provider_rejects_dimension_mismatch(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [1.0, 0.0]}]}

    monkeypatch.setattr("service.core.embeddings.httpx.post", lambda **kwargs: FakeResponse())
    provider = OpenAICompatibleEmbeddingProvider(
        EmbeddingProviderConfig(
            base_url="https://provider.example/v1",
            model="text-embedding-test",
            api_key="embedding-secret",
            dimensions=3,
            batch_size=10,
            timeout_seconds=7,
        )
    )

    with pytest.raises(ValueError, match="dimension"):
        provider.embed_many(["alpha"])


def test_openai_compatible_embedding_provider_rejects_count_mismatch(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

    monkeypatch.setattr("service.core.embeddings.httpx.post", lambda **kwargs: FakeResponse())
    provider = OpenAICompatibleEmbeddingProvider(
        EmbeddingProviderConfig(
            base_url="https://provider.example/v1",
            model="text-embedding-test",
            api_key="embedding-secret",
            dimensions=3,
            batch_size=10,
            timeout_seconds=7,
        )
    )

    with pytest.raises(ValueError, match="count"):
        provider.embed_many(["alpha", "beta"])


def test_hash_embedding_provider_supports_embed_many():
    provider = build_embedding_provider(Settings(embedding_mode="hash", embedding_dimensions=8), active_profile=None)

    embeddings = provider.embed_many(["alpha", "beta"])

    assert len(embeddings) == 2
    assert all(len(vector) == 8 for vector in embeddings)


def test_build_embedding_provider_uses_active_openai_compatible_profile():
    profile = LLMProviderProfile(
        provider="openai-compatible",
        base_url="https://provider.example/v1",
        model="gpt-test",
        api_key="embedding-secret",
        timeout_seconds=9,
        supports_embedding=True,
        embedding_model="text-embedding-test",
        embedding_dimensions=3,
    )

    provider = build_embedding_provider(
        Settings(embedding_dimensions=8, embedding_batch_size=5),
        active_profile=profile,
    )

    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.config.base_url == "https://provider.example/v1"
    assert provider.config.model == "text-embedding-test"
    assert provider.config.api_key == "embedding-secret"
    assert provider.config.dimensions == 3
    assert provider.config.batch_size == 5
    assert provider.config.timeout_seconds == 9


@pytest.mark.parametrize(
    ("provider_name", "api_key", "embedding_model"),
    [
        ("custom-provider", "embedding-secret", "text-embedding-test"),
        ("openai-compatible", None, "text-embedding-test"),
        ("openai-compatible", "embedding-secret", None),
    ],
)
def test_build_embedding_provider_falls_back_for_unsupported_or_incomplete_profile(
    provider_name,
    api_key,
    embedding_model,
):
    profile = LLMProviderProfile(
        provider=provider_name,
        base_url="https://provider.example/v1",
        model="gpt-test",
        api_key=api_key,
        timeout_seconds=9,
        supports_embedding=True,
        embedding_model=embedding_model,
        embedding_dimensions=3,
    )

    provider = build_embedding_provider(Settings(embedding_dimensions=8), active_profile=profile)

    assert isinstance(provider, HashEmbeddingProvider)
    assert provider.dimensions == 8
