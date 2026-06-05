from dataclasses import dataclass

from service.core.chunking import chunk_text
from service.core.embeddings import HashEmbeddingProvider, cosine, dumps_embedding, loads_embedding
from service.models import SourceChunk
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChunkRead


@dataclass
class RankedChunk:
    chunk: SourceChunk
    score: float


class KnowledgeService:
    def __init__(
        self,
        sources: SourceRepository,
        chunks: ChunkRepository,
        embeddings: HashEmbeddingProvider | None = None,
    ):
        self.sources = sources
        self.chunks = chunks
        self.embeddings = embeddings or HashEmbeddingProvider()

    def index_source(self, source_id: int) -> None:
        source = self.sources.get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        self.sources.mark_parsing(source_id)
        text = (source.content or "").strip()
        chunks = chunk_text(text)
        if not chunks:
            self.sources.mark_failed(source_id, "No text content found")
            return
        indexed = [(chunk, dumps_embedding(self.embeddings.embed(chunk))) for chunk in chunks]
        self.chunks.replace_for_source(source_id, indexed)
        self.sources.mark_indexed(source_id)

    def search(self, query: str, limit: int = 5) -> list[ChunkRead]:
        query_vector = self.embeddings.embed(query)
        query_terms = {term.lower() for term in query.split() if term.strip()}
        ranked: list[RankedChunk] = []
        for chunk in self.chunks.list_all():
            vector_score = cosine(query_vector, loads_embedding(chunk.embedding_json))
            keyword_score = sum(1.0 for term in query_terms if term in chunk.text.lower())
            score = vector_score + keyword_score
            if score > 0:
                ranked.append(RankedChunk(chunk=chunk, score=score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return [
            ChunkRead(
                id=item.chunk.id,
                source_id=item.chunk.source_id,
                source_title=item.chunk.source.title,
                text=item.chunk.text,
                score=item.score,
            )
            for item in ranked[:limit]
        ]
