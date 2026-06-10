import re

from service.models import Memory, MemoryCandidate
from service.repositories.memories import MemoryRepository
from service.schemas import (
    MemoryDuplicateSuggestionRead,
    MemoryGraphEdge,
    MemoryGraphNode,
    MemoryGraphRead,
)


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

    def create_relation(
        self,
        source_memory_id: int,
        target_memory_id: int,
        relation_type: str,
        provenance: str = "user",
        strength: int = 70,
    ):
        return self.memories.create_relation(
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type=relation_type,
            provenance=provenance,
            strength=strength,
        )

    def forget_relation(self, relation_id: int):
        return self.memories.forget_relation(relation_id)

    def get_memory_relations(self, memory_id: int):
        return self.memories.list_relations_for_memory(memory_id)

    def build_memory_graph(
        self,
        center_memory_id: int,
        depth: int = 2,
        max_nodes: int = 50,
    ) -> MemoryGraphRead:
        center = self.memories.get(center_memory_id)
        if center is None:
            raise ValueError(f"memory {center_memory_id} not found")

        active_statuses = {"active", "edited"}
        nodes: dict[int, MemoryGraphNode] = {}
        edges: dict[int, MemoryGraphEdge] = {}
        visited: set[int] = set()
        queue: list[tuple[int, int]] = [(center_memory_id, 0)]

        while queue and len(nodes) < max_nodes:
            current_id, current_depth = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            memory = self.memories.get(current_id)
            if memory is None or memory.status not in active_statuses:
                continue

            nodes[current_id] = MemoryGraphNode(
                id=memory.id,
                text=memory.text,
                memory_type=memory.memory_type,
                status=memory.status,
            )

            if current_depth >= depth:
                continue

            relations = self.memories.list_relations_for_memory(current_id)
            for relation in relations:
                if relation.status != "active":
                    continue
                other_id = relation.target_memory_id if relation.source_memory_id == current_id else relation.source_memory_id
                other = self.memories.get(other_id)
                if other is None or other.status not in active_statuses:
                    continue
                if relation.id not in edges:
                    edges[relation.id] = MemoryGraphEdge(
                        id=relation.id,
                        source_memory_id=relation.source_memory_id,
                        target_memory_id=relation.target_memory_id,
                        relation_type=relation.relation_type,
                        provenance=relation.provenance,
                        strength=relation.strength,
                        status=relation.status,
                    )
                if other_id not in visited:
                    queue.append((other_id, current_depth + 1))

        return MemoryGraphRead(
            center_memory_id=center_memory_id,
            nodes=list(nodes.values()),
            edges=list(edges.values()),
        )

    def build_hub_graph(self, limit: int = 5) -> MemoryGraphRead:
        hubs = self.memories.top_memories_by_relation_count(limit)

        if not hubs:
            recent = self.memories.recent_active_memories(limit)
            nodes = [
                MemoryGraphNode(id=m.id, text=m.text, memory_type=m.memory_type, status=m.status)
                for m in recent
            ]
            center_id = nodes[0].id if nodes else 0
            return MemoryGraphRead(center_memory_id=center_id, nodes=nodes, edges=[])

        hub_ids = {m.id for m in hubs}
        nodes = [
            MemoryGraphNode(id=m.id, text=m.text, memory_type=m.memory_type, status=m.status)
            for m in hubs
        ]

        edges: dict[int, MemoryGraphEdge] = {}
        for hub_id in hub_ids:
            for relation in self.memories.list_relations_for_memory(hub_id):
                if relation.status != "active":
                    continue
                if relation.source_memory_id in hub_ids and relation.target_memory_id in hub_ids:
                    if relation.id not in edges:
                        edges[relation.id] = MemoryGraphEdge(
                            id=relation.id,
                            source_memory_id=relation.source_memory_id,
                            target_memory_id=relation.target_memory_id,
                            relation_type=relation.relation_type,
                            provenance=relation.provenance,
                            strength=relation.strength,
                            status=relation.status,
                        )

        return MemoryGraphRead(
            center_memory_id=hubs[0].id,
            nodes=nodes,
            edges=list(edges.values()),
        )

    def promote_duplicate_to_related(self, source_memory_id: int, target_memory_id: int):
        return self.memories.create_relation(
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            relation_type="related_to",
            provenance="system:duplicate-suggestion",
            strength=80,
        )

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
