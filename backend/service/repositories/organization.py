import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from service.models import Favorite, Tag, TagAssignment, TagSuggestion


def normalize_tag_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


class OrganizationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_tags(self) -> list[Tag]:
        stmt = select(Tag).order_by(Tag.name.asc(), Tag.id.asc())
        return list(self.db.scalars(stmt))

    def create_tag(self, name: str, color: str | None = None) -> Tag:
        cleaned = re.sub(r"\s+", " ", name.strip())
        normalized = normalize_tag_name(cleaned)
        existing = self.db.scalar(select(Tag).where(Tag.normalized_name == normalized))
        if existing is not None:
            return existing
        tag = Tag(name=cleaned, normalized_name=normalized, color=color)
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def get_tag(self, tag_id: int) -> Tag | None:
        return self.db.get(Tag, tag_id)

    def assign_tag(self, tag_id: int, target_type: str, target_id: int, source: str = "user") -> TagAssignment:
        existing = self.db.scalar(
            select(TagAssignment)
            .options(selectinload(TagAssignment.tag))
            .where(
                TagAssignment.tag_id == tag_id,
                TagAssignment.target_type == target_type,
                TagAssignment.target_id == target_id,
            )
        )
        if existing is not None:
            return existing
        assignment = TagAssignment(tag_id=tag_id, target_type=target_type, target_id=target_id, source=source)
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        assignment.tag
        return assignment

    def delete_assignment(self, assignment_id: int) -> None:
        assignment = self.db.get(TagAssignment, assignment_id)
        if assignment is not None:
            self.db.delete(assignment)
            self.db.commit()

    def assignments_for_target(self, target_type: str, target_id: int) -> list[TagAssignment]:
        stmt = (
            select(TagAssignment)
            .options(selectinload(TagAssignment.tag))
            .where(TagAssignment.target_type == target_type, TagAssignment.target_id == target_id)
            .order_by(TagAssignment.created_at.desc(), TagAssignment.id.desc())
        )
        return list(self.db.scalars(stmt))

    def list_assignments(self) -> list[TagAssignment]:
        stmt = select(TagAssignment).options(selectinload(TagAssignment.tag)).order_by(TagAssignment.created_at.desc(), TagAssignment.id.desc())
        return list(self.db.scalars(stmt))

    def create_suggestion(self, label: str, target_type: str, target_id: int, reason: str, confidence: int = 70) -> TagSuggestion:
        cleaned = re.sub(r"\s+", " ", label.strip())
        normalized = normalize_tag_name(cleaned)
        existing = list(
            self.db.scalars(
                select(TagSuggestion).where(
                    TagSuggestion.target_type == target_type,
                    TagSuggestion.target_id == target_id,
                )
            )
        )
        for suggestion in existing:
            if normalize_tag_name(suggestion.label) == normalized:
                return suggestion
        suggestion = TagSuggestion(
            label=cleaned,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            confidence=confidence,
        )
        self.db.add(suggestion)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def pending_suggestions(self, target_type: str | None = None, target_id: int | None = None) -> list[TagSuggestion]:
        stmt = select(TagSuggestion).where(TagSuggestion.status == "pending")
        if target_type is not None:
            stmt = stmt.where(TagSuggestion.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(TagSuggestion.target_id == target_id)
        stmt = stmt.order_by(TagSuggestion.created_at.desc(), TagSuggestion.id.desc())
        return list(self.db.scalars(stmt))

    def pending_suggestion_count(self) -> int:
        return len(self.pending_suggestions())

    def confirm_suggestion(self, suggestion_id: int) -> TagAssignment:
        suggestion = self.db.get(TagSuggestion, suggestion_id)
        if suggestion is None:
            raise ValueError(f"suggestion {suggestion_id} not found")
        if suggestion.status != "pending":
            raise ValueError(f"suggestion {suggestion_id} is not pending")
        tag = self.create_tag(suggestion.label)
        assignment = self.assign_tag(tag.id, suggestion.target_type, suggestion.target_id, source="ai-confirmed")
        suggestion.status = "confirmed"
        self.db.commit()
        self.db.refresh(assignment)
        assignment.tag
        return assignment

    def ignore_suggestion(self, suggestion_id: int) -> TagSuggestion:
        suggestion = self.db.get(TagSuggestion, suggestion_id)
        if suggestion is None:
            raise ValueError(f"suggestion {suggestion_id} not found")
        if suggestion.status != "pending":
            raise ValueError(f"suggestion {suggestion_id} is not pending")
        suggestion.status = "ignored"
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def favorite(self, target_type: str, target_id: int) -> Favorite:
        existing = self.db.scalar(select(Favorite).where(Favorite.target_type == target_type, Favorite.target_id == target_id))
        if existing is not None:
            return existing
        favorite = Favorite(target_type=target_type, target_id=target_id)
        self.db.add(favorite)
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def unfavorite(self, target_type: str, target_id: int) -> None:
        favorite = self.db.scalar(select(Favorite).where(Favorite.target_type == target_type, Favorite.target_id == target_id))
        if favorite is not None:
            self.db.delete(favorite)
            self.db.commit()

    def list_favorites(self, target_type: str | None = None) -> list[Favorite]:
        stmt = select(Favorite)
        if target_type is not None:
            stmt = stmt.where(Favorite.target_type == target_type)
        stmt = stmt.order_by(Favorite.created_at.desc(), Favorite.id.desc())
        return list(self.db.scalars(stmt))

    def is_favorite(self, target_type: str, target_id: int) -> bool:
        return self.db.scalar(select(Favorite.id).where(Favorite.target_type == target_type, Favorite.target_id == target_id)) is not None
