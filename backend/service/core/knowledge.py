from dataclasses import dataclass
import re

from service.core.chunking import chunk_text
from service.core.embeddings import HashEmbeddingProvider, cosine, dumps_embedding, loads_embedding
from service.models import SourceChunk
from service.repositories.chunks import ChunkRepository
from service.repositories.indexing_runs import IndexingRunRepository
from service.repositories.sources import SourceRepository
from service.schemas import ChunkRead


_DATE_RE = re.compile(
    r"(?P<year>\d{4})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
    r"|(?P<iso_year>\d{4})[-/.](?P<iso_month>\d{1,2})[-/.](?P<iso_day>\d{1,2})"
)
_LATIN_TERM_RE = re.compile(r"[a-z][a-z0-9_+-]*", re.IGNORECASE)
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_CJK_STOP_TERMS = {"一个", "这个", "那个", "什么", "怎么", "如何", "为何", "哪些", "一下", "是否"}


@dataclass
class RankedChunk:
    chunk: SourceChunk
    score: float
    matched_terms: list[str]
    matched_date: str | None


class KnowledgeService:
    def __init__(
        self,
        sources: SourceRepository,
        chunks: ChunkRepository,
        indexing_runs: IndexingRunRepository | None = None,
        embeddings: HashEmbeddingProvider | None = None,
    ):
        self.sources = sources
        self.chunks = chunks
        self.indexing_runs = indexing_runs or IndexingRunRepository(
            chunks.db,
            user_id=chunks.user_id,
            knowledge_base_id=chunks.knowledge_base_id,
        )
        self.embeddings = embeddings or HashEmbeddingProvider()

    def index_source(self, source_id: int, job_id: int | None = None) -> None:
        source = self.sources.get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} not found")
        embedding_dimensions = getattr(self.embeddings, "dimensions", None)
        run = self.indexing_runs.create(
            run_type="source",
            source_id=source_id,
            knowledge_base_id=source.knowledge_base_id,
            job_id=job_id,
            embedding_provider_profile_id=None,
            embedding_model="local-hash",
            embedding_dimensions=embedding_dimensions,
        )
        try:
            self.indexing_runs.mark_running(run.id)
            self.sources.mark_parsing(source_id)
            text = (source.content or "").strip()
            chunks = chunk_text(text)
            if not chunks:
                message = "No text content found"
                self.sources.mark_failed(source_id, message)
                self.indexing_runs.mark_failed(run.id, message)
                return
            indexed = [(chunk, dumps_embedding(self.embeddings.embed(chunk))) for chunk in chunks]
            self.indexing_runs.update_progress(run.id, chunks_total=len(indexed), chunks_embedded=len(indexed))
            self.chunks.replace_for_source(
                source_id,
                indexed,
                embedding_status="skipped",
                embedding_model="local-hash",
                embedding_dimensions=embedding_dimensions,
                index_status="skipped",
            )
            self.indexing_runs.mark_succeeded(
                run.id,
                chunks_total=len(indexed),
                chunks_embedded=len(indexed),
                chunks_indexed=0,
            )
            self.sources.mark_indexed(source_id)
        except Exception as exc:
            self.indexing_runs.mark_failed(run.id, str(exc))
            raise

    def search(self, query: str, limit: int = 5) -> list[ChunkRead]:
        query_vector = self.embeddings.embed(query)
        query_terms = self._search_terms(query)
        query_dates = self._date_terms(query)
        ranked: list[RankedChunk] = []
        for chunk in self.chunks.list_all():
            searchable_text = f"{chunk.source.title} {chunk.text}"
            chunk_dates = self._date_terms(searchable_text)
            if query_dates and query_dates.isdisjoint(chunk_dates):
                continue
            chunk_terms = self._search_terms(searchable_text)
            matched_terms = sorted(term for term in query_terms if term in chunk_terms)
            keyword_score = float(len(matched_terms))
            if keyword_score <= 0:
                continue
            vector_score = cosine(query_vector, loads_embedding(chunk.embedding_json))
            matched_dates = sorted(query_dates.intersection(chunk_dates))
            matched_date = matched_dates[0] if matched_dates else None
            date_score = 2.0 if matched_date else 0.0
            score = (keyword_score * 2.0) + date_score + vector_score
            ranked.append(RankedChunk(chunk=chunk, score=score, matched_terms=matched_terms, matched_date=matched_date))
        ranked.sort(key=lambda item: item.score, reverse=True)
        results: list[ChunkRead] = []
        seen_texts: set[str] = set()
        for item in ranked:
            focused_text = self._focused_text(item.chunk.text, query_terms, query_dates)
            fingerprint = re.sub(r"\s+", " ", focused_text).strip().lower()
            if fingerprint in seen_texts:
                continue
            seen_texts.add(fingerprint)
            results.append(
                ChunkRead(
                    id=item.chunk.id,
                    source_id=item.chunk.source_id,
                    source_title=item.chunk.source.title,
                    text=focused_text,
                    score=item.score,
                    matched_terms=item.matched_terms,
                    matched_date=item.matched_date,
                    match_reason=self._match_reason(item.matched_terms, item.matched_date),
                )
            )
            if len(results) >= limit:
                break
        return results

    def _match_reason(self, matched_terms: list[str], matched_date: str | None) -> str:
        reasons: list[str] = []
        if matched_date:
            reasons.append(f"匹配日期 {matched_date}")
        if matched_terms:
            reasons.append(f"匹配关键词：{'、'.join(matched_terms[:6])}")
        return "；".join(reasons)

    def _search_terms(self, text: str) -> set[str]:
        lowered = text.lower()
        terms = {match.group(0) for match in _LATIN_TERM_RE.finditer(lowered) if len(match.group(0)) >= 2}
        for match in _CJK_RUN_RE.finditer(lowered):
            run = match.group(0)
            terms.update(run[index : index + 2] for index in range(len(run) - 1))
        return {term for term in terms if term not in _CJK_STOP_TERMS}

    def _date_terms(self, text: str) -> set[str]:
        dates: set[str] = set()
        for match in _DATE_RE.finditer(text):
            year = match.group("year") or match.group("iso_year")
            month = match.group("month") or match.group("iso_month")
            day = match.group("day") or match.group("iso_day")
            if year and month and day:
                dates.add(f"{int(year):04d}-{int(month):02d}-{int(day):02d}")
        return dates

    def _focused_text(self, text: str, query_terms: set[str], query_dates: set[str], window: int = 700) -> str:
        if not text:
            return text
        for match in _DATE_RE.finditer(text):
            year = match.group("year") or match.group("iso_year")
            month = match.group("month") or match.group("iso_month")
            day = match.group("day") or match.group("iso_day")
            if year and month and day and f"{int(year):04d}-{int(month):02d}-{int(day):02d}" in query_dates:
                prefix_start = text.rfind("时间 |", max(0, match.start() - 40), match.start())
                start = prefix_start if prefix_start >= 0 else match.start()
                return text[start : start + window].strip()

        lowered = text.lower()
        positions = [lowered.find(term) for term in query_terms if lowered.find(term) >= 0]
        if not positions:
            return text[:window].strip()
        start = max(0, min(positions) - 120)
        return text[start : start + window].strip()
