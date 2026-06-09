import re

from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.organization import OrganizationRepository
from service.repositories.sources import SourceRepository

_LATIN_LABEL_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]{3,}")
_STOP_LABELS = {"main", "html", "body", "note", "text", "assistant", "user"}
_KNOWN_PHRASES = ["全局搜索", "标签建议", "状态面板", "个人知识库", "匹配原因", "资料索引"]


class TagSuggestionService:
    def __init__(
        self,
        sources: SourceRepository,
        memories: MemoryRepository,
        conversations: ConversationRepository,
        organization: OrganizationRepository,
    ):
        self.sources = sources
        self.memories = memories
        self.conversations = conversations
        self.organization = organization

    def ensure_suggestions_for_existing(self) -> None:
        for source in self.sources.list_all():
            text = "\n".join(part for part in [source.title, source.content, source.url, source.filename] if part)
            for label in self._labels(text):
                self.organization.create_suggestion(label, "source", source.id, f"从资料「{source.title}」中识别到标签线索。", 72)

        for memory in self.memories.list_active_for_search():
            for label in self._labels(f"{memory.memory_type}\n{memory.text}"):
                self.organization.create_suggestion(label, "memory", memory.id, "从已确认记忆中识别到标签线索。", 70)

        for message in self.conversations.list_messages_for_search():
            for label in self._labels(f"{message.conversation.title if message.conversation else ''}\n{message.content}"):
                self.organization.create_suggestion(label, "message", message.id, "从对话内容中识别到标签线索。", 68)

    def _labels(self, text: str, limit: int = 3) -> list[str]:
        labels: list[str] = []
        for match in _LATIN_LABEL_RE.finditer(text):
            label = match.group(0)
            if label.lower() not in _STOP_LABELS and label not in labels:
                labels.append(label)
        for phrase in _KNOWN_PHRASES:
            if phrase in text and phrase not in labels:
                labels.append(phrase)
        if not labels:
            for match in _CJK_RUN_RE.finditer(text):
                label = match.group(0)[:6]
                if label not in labels:
                    labels.append(label)
                    break
        return labels[:limit]
