from service.models import Memory, MemoryCandidate
from service.repositories.memories import MemoryRepository


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

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, Memory]] = []
        for memory in self.memories.active_memories():
            score = sum(1 for term in terms if term in memory.text.lower())
            if score > 0 or not terms:
                scored.append((score, memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:limit]]

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
