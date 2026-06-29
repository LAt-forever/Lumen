import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from service.models import Favorite, Tag, TagAssignment, TagSuggestion


def normalize_tag_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


class OrganizationRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id

    def _tag_filter(self, stmt):
        if self.user_id is not None:
            return stmt.where(Tag.user_id == self.user_id)
        return stmt

    def _assignment_filter(self, stmt):
        if self.user_id is not None:
            return stmt.where(TagAssignment.user_id == self.user_id)
        return stmt

    def _suggestion_filter(self, stmt):
        if self.user_id is not None:
            return stmt.where(TagSuggestion.user_id == self.user_id)
        return stmt

    def _favorite_filter(self, stmt):
        if self.user_id is not None:
            return stmt.where(Favorite.user_id == self.user_id)
        return stmt

    def list_tags(self) -> list[Tag]:
        stmt = self._tag_filter(select(Tag)).order_by(Tag.name.asc(), Tag.id.asc())
        return list(self.db.scalars(stmt))

    def create_tag(self, name: str, color: str | None = None) -> Tag:
        cleaned = re.sub(r"\s+", " ", name.strip())
        normalized = normalize_tag_name(cleaned)
        stmt = select(Tag).where(Tag.normalized_name == normalized)
        if self.user_id is not None:
            stmt = stmt.where(Tag.user_id == self.user_id)
        existing = self.db.scalar(stmt)
        if existing is not None:
            return existing
        tag = Tag(user_id=self.user_id, name=cleaned, normalized_name=normalized, color=color)
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def get_tag(self, tag_id: int) -> Tag | None:
        if self.user_id is None:
            return self.db.get(Tag, tag_id)
        return self.db.scalar(select(Tag).where(Tag.id == tag_id, Tag.user_id == self.user_id))

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
        if self.user_id is not None:
            existing = self.db.scalar(
                select(TagAssignment)
                .options(selectinload(TagAssignment.tag))
                .where(
                    TagAssignment.user_id == self.user_id,
                    TagAssignment.tag_id == tag_id,
                    TagAssignment.target_type == target_type,
                    TagAssignment.target_id == target_id,
                )
            )
        if existing is not None:
            return existing
        assignment = TagAssignment(user_id=self.user_id, tag_id=tag_id, target_type=target_type, target_id=target_id, source=source)
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        assignment.tag
        return assignment

    def delete_assignment(self, assignment_id: int) -> None:
        if self.user_id is None:
            assignment = self.db.get(TagAssignment, assignment_id)
        else:
            assignment = self.db.scalar(select(TagAssignment).where(TagAssignment.id == assignment_id, TagAssignment.user_id == self.user_id))
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
        if self.user_id is not None:
            stmt = stmt.where(TagAssignment.user_id == self.user_id)
        return list(self.db.scalars(stmt))

    def list_assignments(self) -> list[TagAssignment]:
        stmt = select(TagAssignment).options(selectinload(TagAssignment.tag)).order_by(TagAssignment.created_at.desc(), TagAssignment.id.desc())
        if self.user_id is not None:
            stmt = stmt.where(TagAssignment.user_id == self.user_id)
        return list(self.db.scalars(stmt))

    def create_suggestion(self, label: str, target_type: str, target_id: int, reason: str, confidence: int = 70) -> TagSuggestion:
        cleaned = re.sub(r"\s+", " ", label.strip())
        normalized = normalize_tag_name(cleaned)
        existing = list(
            self.db.scalars(
                select(TagSuggestion).where(
                    TagSuggestion.user_id == self.user_id if self.user_id is not None else True,
                    TagSuggestion.target_type == target_type,
                    TagSuggestion.target_id == target_id,
                )
            )
        )
        for suggestion in existing:
            if normalize_tag_name(suggestion.label) == normalized:
                return suggestion
        suggestion = TagSuggestion(
            user_id=self.user_id,
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
        if self.user_id is not None:
            stmt = stmt.where(TagSuggestion.user_id == self.user_id)
        if target_type is not None:
            stmt = stmt.where(TagSuggestion.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(TagSuggestion.target_id == target_id)
        stmt = stmt.order_by(TagSuggestion.created_at.desc(), TagSuggestion.id.desc())
        return list(self.db.scalars(stmt))

    def pending_suggestion_count(self) -> int:
        return len(self.pending_suggestions())

    def confirm_suggestion(self, suggestion_id: int) -> TagAssignment:
        if self.user_id is None:
            suggestion = self.db.get(TagSuggestion, suggestion_id)
        else:
            suggestion = self.db.scalar(select(TagSuggestion).where(TagSuggestion.id == suggestion_id, TagSuggestion.user_id == self.user_id))
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
        if self.user_id is None:
            suggestion = self.db.get(TagSuggestion, suggestion_id)
        else:
            suggestion = self.db.scalar(select(TagSuggestion).where(TagSuggestion.id == suggestion_id, TagSuggestion.user_id == self.user_id))
        if suggestion is None:
            raise ValueError(f"suggestion {suggestion_id} not found")
        if suggestion.status != "pending":
            raise ValueError(f"suggestion {suggestion_id} is not pending")
        suggestion.status = "ignored"
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def favorite(self, target_type: str, target_id: int) -> Favorite:
        stmt = select(Favorite).where(Favorite.target_type == target_type, Favorite.target_id == target_id)
        if self.user_id is not None:
            stmt = stmt.where(Favorite.user_id == self.user_id)
        existing = self.db.scalar(stmt)
        if existing is not None:
            return existing
        favorite = Favorite(user_id=self.user_id, target_type=target_type, target_id=target_id)
        self.db.add(favorite)
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def unfavorite(self, target_type: str, target_id: int) -> None:
        stmt = select(Favorite).where(Favorite.target_type == target_type, Favorite.target_id == target_id)
        if self.user_id is not None:
            stmt = stmt.where(Favorite.user_id == self.user_id)
        favorite = self.db.scalar(stmt)
        if favorite is not None:
            self.db.delete(favorite)
            self.db.commit()

    def list_favorites(self, target_type: str | None = None) -> list[Favorite]:
        stmt = select(Favorite)
        if self.user_id is not None:
            stmt = stmt.where(Favorite.user_id == self.user_id)
        if target_type is not None:
            stmt = stmt.where(Favorite.target_type == target_type)
        stmt = stmt.order_by(Favorite.created_at.desc(), Favorite.id.desc())
        return list(self.db.scalars(stmt))

    def is_favorite(self, target_type: str, target_id: int) -> bool:
        stmt = select(Favorite.id).where(Favorite.target_type == target_type, Favorite.target_id == target_id)
        if self.user_id is not None:
            stmt = stmt.where(Favorite.user_id == self.user_id)
        return self.db.scalar(stmt) is not None
