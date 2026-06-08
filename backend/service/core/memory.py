import re

from service.models import Memory, MemoryCandidate
from service.repositories.memories import MemoryRepository
from service.schemas import MemoryDuplicateSuggestionRead


_LATIN_TERM_RE = re.compile(r"[a-z0-9]+")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


class MemoryService:
    def __init__(self, memories: MemoryRepository):
        self.memories = memories

    def extract_candidates(self, text: str, source_kind: str, source_ref: str) -> list[MemoryCandidate]:
        stripped = text.strip()
        if not stripped:
            return []
        lowered = stripped.lower()
        memory_type = self._classify(stripped, lowered)
        if memory_type is None:
            return []
        candidate_text = self._normalize(stripped, memory_type)
        return [
            self.memories.create_candidate(
                text=candidate_text,
                memory_type=memory_type,
                source_kind=source_kind,
                source_ref=source_ref,
                confidence=72,
            )
        ]

    def confirm(self, candidate_id: int, text: str | None = None, memory_type: str | None = None) -> Memory:
        return self.memories.confirm(candidate_id, text=text, memory_type=memory_type)

    def ignore(self, candidate_id: int) -> None:
        self.memories.ignore(candidate_id)

    def edit(self, memory_id: int, text: str, memory_type: str) -> Memory:
        return self.memories.update(memory_id, text=text, memory_type=memory_type)

    def forget(self, memory_id: int) -> Memory:
        return self.memories.forget(memory_id)

    def merge(self, memory_id: int, target_memory_id: int) -> Memory:
        return self.memories.merge(memory_id, target_memory_id=target_memory_id)

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        terms = self._search_terms(query)
        if not terms:
            return []
        scored: list[tuple[int, Memory]] = []
        for memory in self.memories.active_memories():
            score = sum(1 for term in terms if term in memory.text.lower())
            if score > 0:
                scored.append((score, memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:limit]]

    def duplicate_suggestions(self, threshold: float = 0.6) -> list[MemoryDuplicateSuggestionRead]:
        memories = self.memories.active_memories()
        suggestions: list[MemoryDuplicateSuggestionRead] = []
        for source_index, source in enumerate(memories):
            source_terms = self._search_terms(source.text)
            if not source_terms:
                continue
            for target in memories[source_index + 1 :]:
                target_terms = self._search_terms(target.text)
                if not target_terms:
                    continue
                overlap_score = self._overlap_score(source_terms, target_terms)
                if overlap_score < threshold:
                    continue
                suggestions.append(
                    MemoryDuplicateSuggestionRead(
                        source_memory_id=source.id,
                        target_memory_id=target.id,
                        source_text=source.text,
                        target_text=target.text,
                        overlap_score=round(overlap_score, 3),
                    )
                )
        suggestions.sort(key=lambda item: (-item.overlap_score, item.source_memory_id, item.target_memory_id))
        return suggestions

    def _classify(self, text: str, lowered: str) -> str | None:
        if any(marker in text for marker in ["正在做", "项目", "project"]):
            return "project"
        if any(marker in text for marker in ["喜欢", "偏好", "prefer", "like"]):
            return "preference"
        if any(marker in text for marker in ["目标", "希望", "想要"]):
            return "goal"
        return None

    def _normalize(self, text: str, memory_type: str) -> str:
        if text.endswith("。"):
            return text
        if text.endswith("."):
            return text
        return f"{text}。"

    def _search_terms(self, query: str) -> set[str]:
        stripped = query.strip().lower()
        if not stripped:
            return set()
        terms = {match.group(0) for match in _LATIN_TERM_RE.finditer(stripped) if len(match.group(0)) >= 2}
        for match in _CJK_RUN_RE.finditer(stripped):
            run = match.group(0)
            terms.update(run[index : index + 2] for index in range(len(run) - 1))
        return terms

    def _overlap_score(self, source_terms: set[str], target_terms: set[str]) -> float:
        denominator = min(len(source_terms), len(target_terms))
        if denominator == 0:
            return 0.0
        return len(source_terms.intersection(target_terms)) / denominator
