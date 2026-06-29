import hashlib
import json
import math
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from service.config import Settings
from service.core.security import decrypt_secret
from service.models import LLMProviderProfile

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    base_url: str
    model: str
    api_key: str
    dimensions: int
    batch_size: int = 32
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.dimensions < 1:
            raise ValueError("embedding dimensions must be at least 1")
        if self.batch_size < 1:
            raise ValueError("embedding batch size must be at least 1")


class HashEmbeddingProvider:
    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, config: EmbeddingProviderConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/") + "/"

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.config.batch_size):
            batch = texts[start : start + self.config.batch_size]
            embeddings.extend(self._embed_batch(batch))
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            response = httpx.post(
                url=urljoin(self.base_url, "embeddings"),
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.config.model, "input": texts},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
        except httpx.HTTPError as exc:
            raise ValueError("embedding request failed") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid embedding response") from exc

        if len(embeddings) != len(texts):
            raise ValueError("embedding response count mismatch")
        normalized = []
        for embedding in embeddings:
            if not isinstance(embedding, list):
                raise ValueError("invalid embedding response")
            try:
                vector = [float(value) for value in embedding]
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid embedding response") from exc
            if len(vector) != self.config.dimensions:
                raise ValueError(
                    f"embedding dimension mismatch: expected {self.config.dimensions}, got {len(vector)}"
                )
            normalized.append(vector)
        return normalized


def build_embedding_provider(settings: Settings, active_profile: LLMProviderProfile | None = None):
    if (
        active_profile is not None
        and active_profile.supports_embedding
        and active_profile.provider == "openai-compatible"
    ):
        api_key = decrypt_secret(active_profile.api_key)
        model = active_profile.embedding_model
        if api_key and model:
            return OpenAICompatibleEmbeddingProvider(
                EmbeddingProviderConfig(
                    base_url=active_profile.base_url,
                    model=model,
                    api_key=api_key,
                    dimensions=active_profile.embedding_dimensions or settings.embedding_dimensions,
                    batch_size=settings.embedding_batch_size,
                    timeout_seconds=active_profile.timeout_seconds,
                )
            )
    return HashEmbeddingProvider(dimensions=settings.embedding_dimensions)


def dumps_embedding(vector: list[float]) -> str:
    return json.dumps(vector, separators=(",", ":"))


def loads_embedding(payload: str) -> list[float]:
    data = json.loads(payload)
    return [float(value) for value in data]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
