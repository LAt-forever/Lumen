from sqlalchemy import select
from sqlalchemy.orm import Session

from service.models import Citation, Conversation, Message


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, conversation_id: int | None, title: str) -> Conversation:
        if conversation_id is not None:
            conversation = self.db.get(Conversation, conversation_id)
            if conversation is not None:
                return conversation
        conversation = Conversation(title=title[:300])
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def add_message(self, conversation_id: int, role: str, content: str) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_message(self, message_id: int) -> Message | None:
        return self.db.get(Message, message_id)

    def add_citation(self, message_id: int, source_id: int, chunk_id: int, quote: str) -> Citation:
        citation = Citation(message_id=message_id, source_id=source_id, chunk_id=chunk_id, quote=quote)
        self.db.add(citation)
        self.db.commit()
        self.db.refresh(citation)
        return citation

    def recent_user_questions(self, limit: int = 5) -> list[str]:
        stmt = select(Message.content).where(Message.role == "user").order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def list_messages_for_search(self) -> list[Message]:
        stmt = select(Message).order_by(Message.id.asc())
        return list(self.db.scalars(stmt))
