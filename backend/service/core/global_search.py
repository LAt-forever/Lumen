from dataclasses import dataclass
from datetime import datetime
import re

from service.models import Message, Memory, Source, SourceChunk
from service.repositories.chunks import ChunkRepository
from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository, normalize_tag_name
from service.repositories.sources import SourceRepository
from service.schemas import GlobalSearchResultRead, TagRead


_DATE_RE = re.compile(
    r"(?P<year>\d{4})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
    r"|(?P<iso_year>\d{4})[-/.](?P<iso_month>\d{1,2})[-/.](?P<iso_day>\d{1,2})"
)
_LATIN_TERM_RE = re.compile(r"[a-z][a-z0-9_+-]*", re.IGNORECASE)
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_CJK_STOP_TERMS = {"一个", "这个", "那个", "什么", "怎么", "如何", "为何", "哪些", "一下", "是否"}


@dataclass(frozen=True)
class SearchCandidate:
    result_type: str
    target_id: int
    organization_type: str
    organization_id: int
    title: str
    text: str
    created_at: datetime


class GlobalSearchService:
    def __init__(
        self,
        sources: SourceRepository,
        chunks: ChunkRepository,
        memories: MemoryRepository,
        conversations: ConversationRepository,
        organization: OrganizationRepository,
    ):
        self.sources = sources
        self.chunks = chunks
        self.memories = memories
        self.conversations = conversations
        self.organization = organization

    def search(
        self,
        query: str,
        result_types: set[str] | None = None,
        tag: str | None = None,
        favorite: bool = False,
        limit: int = 20,
    ) -> list[GlobalSearchResultRead]:
        query_terms = self._search_terms(query)
        query_dates = self._date_terms(query)
        tag_filter = normalize_tag_name(tag) if tag else None
        results: list[GlobalSearchResultRead] = []
        for candidate in self._candidates():
            if result_types and candidate.result_type not in result_types:
                continue
            tags = self._tags(candidate.organization_type, candidate.organization_id)
            is_favorite = self.organization.is_favorite(candidate.organization_type, candidate.organization_id)
            if favorite and not is_favorite:
                continue
            if tag_filter and not any(normalize_tag_name(tag_item.name) == tag_filter for tag_item in tags):
                continue
            scored = self._score(candidate, query_terms, query_dates, tags, is_favorite)
            if scored is None:
                continue
            score, matched_terms, matched_date, match_reason = scored
            results.append(
                GlobalSearchResultRead(
                    result_type=candidate.result_type,
                    target_id=candidate.target_id,
                    title=candidate.title,
                    snippet=self._snippet(candidate.text, query_terms, query_dates),
                    score=round(score, 3),
                    matched_terms=matched_terms,
                    matched_date=matched_date,
                    match_reason=match_reason,
                    tags=tags,
                    is_favorite=is_favorite,
                    created_at=candidate.created_at,
                )
            )
        results.sort(key=lambda item: (item.score, item.created_at), reverse=True)
        return results[:limit]

    def _candidates(self) -> list[SearchCandidate]:
        candidates: list[SearchCandidate] = []
        for chunk in self.chunks.list_all():
            candidates.append(self._chunk_candidate(chunk))
        for source in self.sources.list_all():
            candidates.append(self._source_candidate(source))
        for memory in self.memories.list_active_for_search():
            candidates.append(self._memory_candidate(memory))
        for message in self.conversations.list_messages_for_search():
            candidates.append(self._message_candidate(message))
        return candidates

    def _chunk_candidate(self, chunk: SourceChunk) -> SearchCandidate:
        return SearchCandidate(
            result_type="source_chunk",
            target_id=chunk.id,
            organization_type="source",
            organization_id=chunk.source_id,
            title=chunk.source.title,
            text=f"{chunk.source.title}\n{chunk.text}",
            created_at=chunk.created_at,
        )

    def _source_candidate(self, source: Source) -> SearchCandidate:
        text = "\n".join(part for part in [source.title, source.content, source.url, source.filename] if part)
        return SearchCandidate(
            result_type="source",
            target_id=source.id,
            organization_type="source",
            organization_id=source.id,
            title=source.title,
            text=text,
            created_at=source.created_at,
        )

    def _memory_candidate(self, memory: Memory) -> SearchCandidate:
        return SearchCandidate(
            result_type="memory",
            target_id=memory.id,
            organization_type="memory",
            organization_id=memory.id,
            title=f"记忆：{memory.memory_type}",
            text=f"{memory.memory_type}\n{memory.text}\n{memory.provenance}",
            created_at=memory.created_at,
        )

    def _message_candidate(self, message: Message) -> SearchCandidate:
        title = f"{'回答' if message.role == 'assistant' else '消息'} #{message.id}"
        conversation_title = message.conversation.title if message.conversation else ""
        return SearchCandidate(
            result_type="message",
            target_id=message.id,
            organization_type="message",
            organization_id=message.id,
            title=title,
            text=f"{conversation_title}\n{message.role}\n{message.content}",
            created_at=message.created_at,
        )

    def _tags(self, target_type: str, target_id: int) -> list[TagRead]:
        return [TagRead.model_validate(assignment.tag) for assignment in self.organization.assignments_for_target(target_type, target_id)]

    def _score(
        self,
        candidate: SearchCandidate,
        query_terms: set[str],
        query_dates: set[str],
        tags: list[TagRead],
        is_favorite: bool,
    ) -> tuple[float, list[str], str | None, str] | None:
        lowered = candidate.text.lower()
        matched_terms = sorted(term for term in query_terms if term in lowered)
        candidate_dates = self._date_terms(candidate.text)
        matched_dates = sorted(query_dates.intersection(candidate_dates))
        matched_date = matched_dates[0] if matched_dates else None
        tag_matches = [tag.name for tag in tags if normalize_tag_name(tag.name) in query_terms]
        if not matched_terms and not matched_date and not tag_matches:
            return None
        score = float(len(matched_terms)) * 2.0
        if matched_date:
            score += 3.0
        if candidate.title and any(term in candidate.title.lower() for term in query_terms):
            score += 1.2
        if tag_matches:
            score += 1.0
        if is_favorite:
            score += 0.5
        reasons: list[str] = []
        if matched_date:
            reasons.append(f"匹配日期 {matched_date}")
        if matched_terms:
            reasons.append(f"匹配关键词：{'、'.join(matched_terms[:6])}")
        if tag_matches:
            reasons.append(f"匹配标签：{'、'.join(tag_matches[:3])}")
        if is_favorite:
            reasons.append("已收藏")
        return score, matched_terms[:8], matched_date, "；".join(reasons)

    def _search_terms(self, text: str) -> set[str]:
        lowered = text.strip().lower()
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

    def _snippet(self, text: str, query_terms: set[str], query_dates: set[str], window: int = 260) -> str:
        if not text:
            return ""
        for match in _DATE_RE.finditer(text):
            year = match.group("year") or match.group("iso_year")
            month = match.group("month") or match.group("iso_month")
            day = match.group("day") or match.group("iso_day")
            if year and month and day and f"{int(year):04d}-{int(month):02d}-{int(day):02d}" in query_dates:
                return text[max(0, match.start() - 30) : match.start() + window].strip()
        lowered = text.lower()
        positions = [lowered.find(term) for term in query_terms if lowered.find(term) >= 0]
        if positions:
            start = max(0, min(positions) - 60)
            return text[start : start + window].strip()
        return text[:window].strip()
